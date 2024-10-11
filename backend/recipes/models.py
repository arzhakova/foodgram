import random
import string

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import UniqueConstraint

User = get_user_model()

STR_LIMIT = 21
MAX_LENGTH = 256
MIN_TIME = 1
MAX_CODE_LENGTH = 6
MIN_INGREDIENT_AMOUNT = 1


class Tag(models.Model):
    """Модель тега."""
    name = models.CharField(
        max_length=MAX_LENGTH,
        verbose_name='Название тега',
        unique=True
    )
    slug = models.SlugField(
        verbose_name='Идентификатор тега',
        unique=True
    )

    class Meta:
        ordering = ('name',)
        verbose_name = 'тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        return self.name[:STR_LIMIT]


class Ingredient(models.Model):
    """Модель ингредиента."""
    name = models.CharField(
        max_length=MAX_LENGTH,
        verbose_name='Название ингредиента',
    )
    measurement_unit = models.CharField(
        max_length=MAX_LENGTH,
        verbose_name='Единица измерения'
    )

    class Meta:
        ordering = ('name',)
        verbose_name = 'ингредиент'
        verbose_name_plural = 'Ингредиенты'
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'measurement_unit'],
                name='unique_ingredient_unit',
            )
        ]

    def __str__(self):
        return f'{self.name[:STR_LIMIT]}, {self.measurement_unit}'


class Recipe(models.Model):
    """Модель рецепта."""
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Автор рецепта'
    )
    name = models.CharField(
        verbose_name='Название рецепта',
        max_length=MAX_LENGTH
    )
    image = models.ImageField(
        blank=True,
        verbose_name='Изображение рецепта',
        upload_to='recipes'
    )
    text = models.TextField(
        verbose_name='Описание рецепта'
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='IngredientInRecipe',
        verbose_name='Ингредиенты рецепта'
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Теги'
    )
    cooking_time = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(MIN_TIME, f'Минимальное время - {MIN_TIME}')
        ],
        verbose_name='Время приготовления, мин.'
    )
    short_code = models.CharField(
        max_length=MAX_CODE_LENGTH,
        unique=True,
        blank=True,
        editable=False,
        verbose_name='Короткий идентификатор'
    )
    pub_date = models.DateTimeField(
        verbose_name='Дата публикации',
        auto_now_add=True
    )

    class Meta:
        default_related_name = 'recipes'
        ordering = ('-pub_date',)
        verbose_name = 'рецепт'
        verbose_name_plural = 'Рецепты'

    def __str__(self):
        return self.name[:STR_LIMIT]

    def generate_short_code(self):
        characters = string.ascii_lowercase + string.digits
        while True:
            short_code = ''.join(random.choices(characters, k=MAX_CODE_LENGTH))
            if not Recipe.objects.filter(short_code=short_code).exists():
                return short_code

    def save(self, *args, **kwargs):
        if not self.short_code:
            self.short_code = self.generate_short_code()
        super().save(*args, **kwargs)


class IngredientInRecipe(models.Model):
    """Модель для связи ингредиента и рецепта."""
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент в рецепте',
    )
    amount = models.IntegerField(
        validators=[
            MinValueValidator(
                MIN_INGREDIENT_AMOUNT,
                f'Минимальное количество - {MIN_INGREDIENT_AMOUNT}'
            )
        ],
        verbose_name='Количество ингредиента'
    )

    class Meta:
        default_related_name = 'ingredient_in_recipe'
        constraints = [
            UniqueConstraint(
                fields=['ingredient', 'recipe'],
                name='unique_ingredient_recipe'),
        ]
        verbose_name = 'ингредиент в рецепте'
        verbose_name_plural = 'Ингредиенты в рецепте'

    def __str__(self):
        return f'{self.ingredient.name} – {self.amount}'


class Favorite(models.Model):
    """Модель избранного."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        default_related_name = 'favorites'
        verbose_name = 'избранное'
        verbose_name_plural = 'Избранное'
        constraints = [
            UniqueConstraint(
                fields=['user', 'recipe'], name='unique_favorite'
            )
        ]

    def __str__(self):
        return f'{self.user} добавил "{self.recipe.name}" в Избранное'


class ShoppingCart(models.Model):
    """Модель корзины покупок."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт для покупки',
    )

    class Meta:
        default_related_name = 'shopping_cart'
        verbose_name = 'корзина покупок'
        verbose_name_plural = 'Корзина покупок'
        constraints = [
            UniqueConstraint(
                fields=['user', 'recipe'], name='unique_shopping_cart'
            )
        ]

    def __str__(self):
        return f'{self.user} добавил "{self.recipe.name}" в корзину покупок'
