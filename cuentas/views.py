from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .forms import CrearUsuarioForm


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def crear_usuario(request):
    # SOLO Administrador puede crear usuarios
    if not request.user.rol or request.user.rol.nombre != "Administrador":
        return HttpResponseForbidden("No autorizado")

    if request.method == "POST":
        form = CrearUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.rol = form.cleaned_data["rol"]
            user.save()
            return redirect("dashboard")  # o donde quieras
    else:
        form = CrearUsuarioForm()

    return render(request, "cuentas/crear_usuario.html", {"form": form})
