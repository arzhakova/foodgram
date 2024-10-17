from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.filters import IngredientFilter, RecipeFilter
from api.pagination import PageLimitPagination
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    AvatarSerializer, FavoriteSerializer, FollowSerializer,
    IngredientSerializer, RecipeReadSerializer, RecipeWriteSerializer,
    RecipeShortSerializer, ShoppingCartSerializer, SubscriptionSerializer,
    TagSerializer, UserSerializer
)
from recipes.models import (
    Favorite, Ingredient, IngredientInRecipe, Recipe, ShoppingCart, Tag
)
from users.models import Follow

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    """Работа с пользователями."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = PageLimitPagination
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ('username', 'email')
    ordering_fields = ('username', 'email')

    def get_permissions(self):
        if self.action in ['retrieve', 'list', 'create']:
            return (permissions.AllowAny(),)
        return (permissions.IsAuthenticated(),)

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=(permissions.IsAuthenticated,)
    )
    def me(self, request, *args, **kwargs):
        """Просмотр информации о пользователе."""
        return super().me(request, *args, **kwargs)

    @action(
        detail=False,
        methods=['PUT'],
        permission_classes=(permissions.IsAuthenticated,),
        url_path='me/avatar'
    )
    def update_avatar(self, request):
        """Загрузка аватара пользователя."""
        serializer = AvatarSerializer(
            request.user,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @update_avatar.mapping.delete
    def delete_avatar(self, request):
        """удаление аватара пользователя."""
        if request.user.avatar:
            request.user.avatar.delete()
            return Response({'detail': 'Аватар успешно удален'},
                            status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Аватар не найден'},
                        status=status.HTTP_404_NOT_FOUND)

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
        serializer = SubscriptionSerializer(
            page,
            many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=['POST'],
        permission_classes=(permissions.IsAuthenticated,)
    )
    def subscribe(self, request, id):
        author = get_object_or_404(User, pk=id)
        serializer = FollowSerializer(
            data={
                'author': author.id,
                'user': request.user.id
            },
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def unsubscribe(self, request, id):
        author = get_object_or_404(User, pk=id)
        subscription_deleted, _ = Follow.objects.filter(
            user=request.user, author=author
        ).delete()
        if not subscription_deleted:
            return Response(
                {'detail': 'Вы не подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = PageLimitPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def add_recipe(self, serializer_cl, request, pk):
        recipe = get_object_or_404(Recipe, pk=pk)
        data = {
            'recipe': recipe.id,
            'user': request.user.id,
        }
        serializer = serializer_cl(
            data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            RecipeShortSerializer(recipe).data, status=status.HTTP_201_CREATED
        )

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
            return self.add_recipe(FavoriteSerializer, request, pk)
        return self.delete_recipe(Favorite, request.user, pk)

    @action(detail=True, methods=['POST', 'DELETE'],
            permission_classes=(permissions.IsAuthenticated,), )
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self.add_recipe(ShoppingCartSerializer, request, pk)
        return self.delete_recipe(ShoppingCart, request.user, pk)

    @action(detail=True, methods=['GET'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        short_link = request.build_absolute_uri(
            f'{settings.SHORT_LINK_PREFIX}/{recipe.short_code}/'
        )
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)

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
                'ingredient__name',
                'ingredient__measurement_unit',
            )
            .order_by('ingredient__name')
            .annotate(total=Sum('amount'))
        )
        shopping_list = ['Список покупок\n']
        shopping_list += [
            f'{ingredient["ingredient__name"]} - '
            f'{ingredient["total"]} '
            f'({ingredient["ingredient__measurement_unit"]})\n'
            for ingredient in ingredients
        ]
        response = HttpResponse(shopping_list, content_type='text/plain')
        response[
            'Content-Disposition'
        ] = 'attachment; filename="shopping_list.txt"'
        return response
