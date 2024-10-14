from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets

from recipes.models import Recipe


class ShortLinkViewSet(viewsets.ViewSet):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def redirect_short_link(self, request, short_code=None):
        recipe = get_object_or_404(Recipe, short_code=short_code)
        return HttpResponseRedirect(
            request.build_absolute_uri(f'/recipes/{recipe.id}')
        )
