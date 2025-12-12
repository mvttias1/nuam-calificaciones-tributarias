from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views

def redirect_to_login(request):
    return redirect("login")

urlpatterns = [
    path("", redirect_to_login, name="home"),
    path("admin/", admin.site.urls),

    path(
        "cuentas/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path("cuentas/", include("cuentas.urls")),
    path("", include("tributaria.urls")),
]
