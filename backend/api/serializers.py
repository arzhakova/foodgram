from django.contrib.auth import get_user_model
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from recipes.models import Ingredient, Recipe, Tag, IngredientInRecipe

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    avatar = Base64ImageField(read_only=True)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password',
            'avatar',
            'is_subscribed'
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        view = self.context.get('view')
        if view and hasattr(view, 'basename') and view.basename == 'recipes':
            return representation
        if request and request.method == 'POST':
            representation.pop('avatar', None)
            representation.pop('is_subscribed', None)
        return representation

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request.user.is_authenticated:
            return request.user.follower.filter(author=obj).exists()
        return False

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('avatar',)


class PasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField()
    current_password = serializers.CharField()


class RecipeSubscribeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SubscribeSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.ReadOnlyField(source='recipes.count')
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes',
            'recipes_count',
            'avatar',
        )
        read_only_fields = ('email', 'username', 'first_name', 'last_name')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user.follower.filter(
                author=obj).exists()
        return False

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[: int(limit)]
        serializer = RecipeSubscribeSerializer(recipes, many=True)
        return serializer.data

    def get_avatar(self, obj):
        if obj.avatar:
            return self.context.get('request').build_absolute_uri(
                obj.avatar.url
            )
        return None


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient.id'
    )
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        many=True, source='ingredient_in_recipe'
    )
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def validate_ingredients(self, value):
        if not value:
            raise ValidationError('Нужен хотя бы один ингредиент!')
        unique_ingredients = set()
        for item in value:
            ingredient_id = item['ingredient']['id']
            if ingredient_id in unique_ingredients:
                raise ValidationError('Ингредиенты должны быть уникальными.')
            unique_ingredients.add(ingredient_id)
        return value

    def validate_tags(self, value):
        if not value:
            raise ValidationError('Нужно выбрать хотя бы один тег!')
        unique_tags = set()
        for tag_id in value:
            if not Tag.objects.filter(id=tag_id).exists():
                raise ValidationError(f'Тег с ID {tag_id} не существует.')
            if tag_id in unique_tags:
                raise ValidationError('Теги должны быть уникальными.')
            unique_tags.add(tag_id)
        return value

    def validate_image(self, value):
        if not value:
            raise ValidationError('Изображение является обязательным.')
        return value

    def create_recipe_ingredients(self, recipe, ingredients_data):
        recipe_ingredients = [
            IngredientInRecipe(
                recipe=recipe,
                ingredient=ingredient['ingredient']['id'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients_data
        ]
        IngredientInRecipe.objects.bulk_create(recipe_ingredients)

    def create(self, validated_data):
        tags_data = self.initial_data.get('tags', None)
        ingredients_data = validated_data.pop('ingredient_in_recipe', None)
        image_data = validated_data.get('image', None)

        self.validate_tags(tags_data)
        self.validate_ingredients(ingredients_data)
        self.validate_image(image_data)

        recipe = Recipe.objects.create(**validated_data)
        self.create_recipe_ingredients(recipe, ingredients_data)
        recipe.tags.set(tags_data)
        return recipe

    def update(self, instance, validated_data):
        tags_data = self.initial_data.get('tags', [])
        ingredients_data = validated_data.pop('ingredient_in_recipe', [])
        image_data = validated_data.pop('image', None)

        self.validate_tags(tags_data)
        self.validate_ingredients(ingredients_data)
        self.validate_image(image_data)

        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get('cooking_time',
                                                   instance.cooking_time)
        if image_data:
            instance.image = image_data

        instance.save()
        instance.tags.set(tags_data)
        instance.ingredient_in_recipe.all().delete()
        self.create_recipe_ingredients(instance, ingredients_data)
        return instance

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        return not user.is_anonymous and user.favorites.filter(
            recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        return not user.is_anonymous and user.shopping_cart.filter(
            recipe=obj).exists()


class RecipeShortSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'cooking_time',
        )
