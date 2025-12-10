from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def logout_view(request):
    """
    Cierra la sesión del usuario y lo redirige al login.
    Acepta GET sin problema.
    """
    logout(request)
    return redirect('login')  # usa el nombre de la URL de login
