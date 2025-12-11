# config/context_processors.py
def rol_usuario(request):
    """
    Entrega el nombre de rol del usuario logeado como 'rol_nombre'
    para usarlo directamente en los templates.
    Ajusta los accesos según tu modelo real.
    """
    rol_nombre = None

    if request.user.is_authenticated:
        # Intenta varias formas de encontrar el rol,
        # adapta esto a cómo lo tienes en tu proyecto.
        try:
            # Ejemplo: User -> perfil -> rol -> nombre
            rol_nombre = request.user.perfil.rol.nombre
        except AttributeError:
            try:
                # Ejemplo alternativo: User -> rol -> nombre
                rol_nombre = request.user.rol.nombre
            except AttributeError:
                rol_nombre = None

    return {"rol_nombre": rol_nombre}
