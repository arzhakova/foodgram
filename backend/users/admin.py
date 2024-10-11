from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin

from .models import Follow

User = get_user_model()


class UserAdmin(DefaultUserAdmin):
    list_display = ('username', 'id', 'email', 'first_name', 'last_name')
    search_fields = ('email', 'username')


class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'author')


admin.site.register(User, UserAdmin)
admin.site.register(Follow, FollowAdmin)
