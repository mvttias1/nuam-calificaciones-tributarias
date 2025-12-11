from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Login usando el template registration/login.html
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),

    # Logout usando nuestra vista propia (acepta GET sin problemas)
    path("logout/", views.logout_view, name="logout"),
]
