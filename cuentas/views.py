from django.contrib.auth import logout
from django.shortcuts import redirect



def logout_view(request):
    """
    Cierra la sesión del usuario y lo redirige al login.
    Acepta GET sin drama, así que el botón puede ser un simple <a>.
    """
    logout(request)
    return redirect("login")