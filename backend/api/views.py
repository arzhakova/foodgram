from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .filters import IngredientFilter, RecipeFilter
from .pagination import PageLimitPagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (AvatarSerializer, SubscribeSerializer,
                          PasswordSerializer, UserSerializer,
                          IngredientSerializer, TagSerializer,
                          RecipeShortSerializer, RecipeSerializer)
from recipes.models import (Ingredient, Tag, Recipe, Favorite, ShoppingCart,
                            IngredientInRecipe)
from users.models import Follow

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """Работа с пользователями."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = PageLimitPagination
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ('username', 'email')
    ordering_fields = ('username', 'email')
    ordering = ('username',)

    def get_permissions(self):
        if self.action in ['retrieve', 'list', 'create']:
            return (permissions.AllowAny(),)
        return (permissions.IsAuthenticated(),)

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=(permissions.IsAuthenticated,)
    )
    def me(self, request):
        """Просмотр информации о пользователе."""
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['PUT', 'DELETE'],
        permission_classes=(permissions.IsAuthenticated,),
        url_path='me/avatar'
    )
    def update_avatar(self, request):
        """Загрузка и удаление аватара пользователя."""
        if request.method == 'PUT':
            avatar = request.data.get('avatar')
            if not avatar:
                raise ValidationError('Необходимо добавить аватар.')
            serializer = AvatarSerializer(
                request.user,
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            if request.user.avatar:
                request.user.avatar.delete()
                return Response({'detail': 'Аватар успешно удален'},
                                status=status.HTTP_204_NO_CONTENT)
            return Response({'detail': 'Аватар не найден'},
                            status=status.HTTP_404_NOT_FOUND)

    @action(
        detail=False,
        methods=['POST'],
        permission_classes=(permissions.IsAuthenticated,)
    )
    def set_password(self, request):
        """Изменение пароля."""
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if request.user.check_password(password):
            request.user.set_password(new_password)
            request.user.save()
            return Response({'detail': 'Пароль успешно обновлен.'},
                            status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Неверный текущий пароль.'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=(permissions.IsAuthenticated,),
    )
    def subscriptions(self, request):
        """Просмотр подписок пользователя."""
        queryset = User.objects.filter(
            following__user=request.user).prefetch_related(
            'recipes').order_by('pk')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SubscribeSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = SubscribeSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=(permissions.IsAuthenticated,),
        url_path='subscribe'
    )
    def edit_subscriptions(self, request, pk=None):
        """Подписка на пользователей."""
        user = request.user
        author = get_object_or_404(User, pk=pk)

        if request.method == 'POST':
            return self.subscribe_user(user, author)

        elif request.method == 'DELETE':
            return self.unsubscribe_user(user, author)

    def subscribe_user(self, user, author):
        if user == author:
            return Response({"detail": "Нельзя подписаться на самого себя."},
                            status=status.HTTP_400_BAD_REQUEST)
        follow, created = Follow.objects.get_or_create(
            user=user,
            author=author
        )
        if not created:
            return Response(
                {'detail': 'Вы уже подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = SubscribeSerializer(
            author, context={"request": self.request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def unsubscribe_user(self, user, author):
        subscription = user.follower.filter(author=author)
        if subscription.exists():
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {'detail': 'Вы не подписаны на этого пользователя.'},
            status=status.HTTP_400_BAD_REQUEST
        )


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_class = IngredientFilter
    search_fields = ('name',)
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    pagination_class = PageLimitPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return (permissions.AllowAny(),)
        if self.action == 'create':
            return (permissions.IsAuthenticated(),)
        if self.action in ('delete', 'destroy', 'update', 'partial_update'):
            return (IsAuthorOrReadOnly(),)
        return super().get_permissions()

    def add_recipe(self, model, user, pk):
        if model.objects.filter(user=user, recipe_id=pk).exists():
            return Response(
                {'errors': 'Рецепт уже добавлен!'},
                status=status.HTTP_400_BAD_REQUEST
            )
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = RecipeShortSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_recipe(self, model, user, pk):
        recipe = get_object_or_404(Recipe, id=pk)
        deleted, _ = model.objects.filter(user=user, recipe=recipe).delete()
        if not deleted:
            return Response(
                {'errors': 'Рецепт не найден!'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['POST', 'DELETE'],
            permission_classes=(permissions.IsAuthenticated,), )
    def favorite(self, request, pk=None):
        if request.method == 'POST':
            return self.add_recipe(Favorite, request.user, pk)
        return self.delete_recipe(Favorite, request.user, pk)

    @action(detail=True, methods=['POST', 'DELETE'],
            permission_classes=(permissions.IsAuthenticated,), )
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self.add_recipe(ShoppingCart, request.user, pk)
        return self.delete_recipe(ShoppingCart, request.user, pk)

    @action(detail=True, methods=['GET'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        short_link = request.build_absolute_uri(f'/s/{recipe.short_code}/')
        return Response({"short-link": short_link}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=(permissions.IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        ingredients = (
            IngredientInRecipe.objects.filter(
                recipe__shopping_cart__user=request.user
            )
            .values(
                "ingredient__name",
                "ingredient__measurement_unit",
            )
            .order_by("ingredient__name")
            .annotate(total=Sum("amount"))
        )
        shopping_list = ["Список покупок\n"]
        shopping_list += [
            f'{ingredient["ingredient__name"]} - '
            f'{ingredient["total"]} '
            f'({ingredient["ingredient__measurement_unit"]})\n'
            for ingredient in ingredients
        ]
        response = HttpResponse(shopping_list, content_type="text/plain")
        response[
            "Content-Disposition"
        ] = 'attachment; filename="shopping_list.txt"'
        return response


class ShortLinkViewSet(viewsets.ViewSet):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def redirect_short_link(self, request, short_code=None):
        recipe = get_object_or_404(Recipe, short_code=short_code)
        return HttpResponseRedirect(
            request.build_absolute_uri(f'/recipes/{recipe.id}')
        )
