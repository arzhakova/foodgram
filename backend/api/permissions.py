from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.IsAuthenticatedOrReadOnly):
    """Пермишн с правами доступа для авторов."""

    def has_object_permission(self, request, view, obj):
        return (request.method in permissions.SAFE_METHODS or request.user
                == obj.author)
