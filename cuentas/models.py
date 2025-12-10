from django.contrib.auth.models import AbstractUser
from django.db import models


class Rol(models.Model):
    """
    Rol del sistema:
    - Corredor
    - Analista
    - Auditor
    - Administrador
    - Gerente
    """
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    """
    Usuario personalizado vinculado a un Rol.
    """
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        if self.rol:
            return f"{self.username} ({self.rol})"
        return self.username
