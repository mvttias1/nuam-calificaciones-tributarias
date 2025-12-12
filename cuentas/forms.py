from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario, Rol


class CrearUsuarioForm(UserCreationForm):
    rol = forms.ModelChoiceField(
        queryset=Rol.objects.filter(nombre__in=["Corredor", "Analista"]),
        required=True,
        empty_label="Seleccione un rol"
    )

    class Meta:
        model = Usuario
        fields = ("username", "email", "rol", "password1", "password2")
