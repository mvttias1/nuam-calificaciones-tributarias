from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def rol_requerido(*roles_permitidos):
    """
    Decorador por roles (basado en request.user.rol.nombre).

    Uso:
        @rol_requerido("Administrador")
        def mi_vista(...):

        @rol_requerido("Administrador", "Gerente")
        def otra_vista(...):
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Si tu Usuario tiene FK 'rol', esto existe:
            rol = getattr(request.user, "rol", None)

            # Si no tiene rol asignado, no pasa
            if not rol or not getattr(rol, "nombre", None):
                raise PermissionDenied("No tienes un rol asignado.")

            if rol.nombre not in roles_permitidos:
                raise PermissionDenied("No tienes permisos para acceder a esta sección.")

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator


def solo_admin(view_func):
    """
    Atajo: solo Administrador.
    """
    return rol_requerido("Administrador")(view_func)
