from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Rol


@receiver(post_migrate)
def crear_roles_basicos(sender, **kwargs):
    """
    Crea los roles básicos de NUAM si no existen.
    Se ejecuta después de 'migrate'.
    """
    if sender.name != 'cuentas':
        return

    roles_definidos = [
        ("Corredor", "Puede subir archivos tributarios y ver calificaciones."),
        ("Analista", "Valida reglas tributarias y puede crear calificaciones."),
        ("Administrador", "Control total del sistema (CRUD completo)."),
        ("Auditor", "Puede ver bitácora y reportes."),
        ("Gerente", "Visualiza panel de indicadores (Dashboard)."),
    ]

    for nombre, descripcion in roles_definidos:
        Rol.objects.get_or_create(nombre=nombre, defaults={'descripcion': descripcion})

    print(">>> Roles básicos de NUAM verificados/creados.")
