from functools import wraps
from django.http import HttpResponseForbidden


def rol_requerido(*roles_permitidos):
    """
    Restringe el acceso a usuarios que tengan alguno de los roles indicados.
    - roles_permitidos: nombres de rol, ej: ('Administrador', 'Analista')
    Nota: los superusuarios (is_superuser=True) siempre pueden acceder.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return HttpResponseForbidden("No estás autenticado.")

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            if not hasattr(user, "rol") or user.rol is None:
                return HttpResponseForbidden("No tienes un rol asignado en el sistema.")

            if user.rol.nombre not in roles_permitidos:
                return HttpResponseForbidden("No tienes permisos para acceder a esta funcionalidad.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

