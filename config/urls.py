from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


def redirect_to_login(request):
    return redirect('login')  # Redirige al login automáticamente

urlpatterns = [
    path('', redirect_to_login),          # <--- redirección principal
    path('admin/', admin.site.urls),
    path('cuentas/', include('django.contrib.auth.urls')),
    path('', include('tributaria.urls')),
    path("cuentas/logout/", auth_views.LogoutView.as_view(), name="logout"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
