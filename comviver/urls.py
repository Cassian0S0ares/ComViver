from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.storage import servir_media_protegida

urlpatterns = [
    path("admin/", admin.site.urls),
    # Midia sempre passa pela checagem de login e perfil, inclusive em
    # desenvolvimento: servir sem checagem vazaria em qualquer demonstracao.
    path("media/<path:caminho>", servir_media_protegida, name="media_protegida"),
    path("", include("accounts.urls")),
    path("", include("acolhidos.urls")),
    path("", include("doacoes.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
