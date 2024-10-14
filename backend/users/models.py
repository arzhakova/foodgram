from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models import F, Q, UniqueConstraint, CheckConstraint

from users.constants import MAX_EMAIL_LENGTH, MAX_USER_LENGTH


class User(AbstractUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = (
        'username',
        'first_name',
        'last_name'
    )
    email = models.EmailField(
        max_length=MAX_EMAIL_LENGTH,
        unique=True,
        verbose_name='Электронная почта',
        help_text='Обязательное поле.'
    )
    username = models.CharField(
        max_length=MAX_USER_LENGTH,
        unique=True,
        help_text='Обязательное поле.',
        validators=[UnicodeUsernameValidator()],
        verbose_name='Юзернейм',
        error_messages={
            'unique': 'Пользователь с таким именем уже существует.',
        },
    )
    first_name = models.CharField(
        max_length=MAX_USER_LENGTH,
        verbose_name='Имя',
        help_text='Обязательное поле.'
    )
    last_name = models.CharField(
        max_length=MAX_USER_LENGTH,
        verbose_name='Фамилия',
        help_text='Обязательное поле.'
    )
    avatar = models.ImageField(
        upload_to='users',
        null=True,
        blank=True,
        verbose_name='Аватар',
    )

    class Meta:
        ordering = ('username',)
        verbose_name = 'пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Follow(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name='Кто подписан',
        on_delete=models.CASCADE,
        related_name='follower'
    )
    author = models.ForeignKey(
        User,
        verbose_name='На кого подписан',
        on_delete=models.CASCADE,
        related_name='following'
    )

    class Meta:
        verbose_name = 'подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            UniqueConstraint(
                fields=['user', 'author'],
                name='unique_follow'
            ),
            CheckConstraint(
                check=~Q(user=F('author')),
                name='no_self_follow'
            ),
        ]

    def __str__(self):
        return f'{self.user} подписался на {self.author}'
