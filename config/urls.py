from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


def redirect_to_login(request):
    # Redirige a la página de login por defecto
    return redirect("login")


urlpatterns = [
    path("", redirect_to_login, name="home"),            # raíz -> login
    path("admin/", admin.site.urls),

    # app de cuentas (login, registro, etc.)
    path("cuentas/", include("cuentas.urls")),

    # app principal
    path("", include("tributaria.urls")),

    # LOGOUT correcto (nota: va bajo /cuentas/logout/)
    path(
        "cuentas/logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
