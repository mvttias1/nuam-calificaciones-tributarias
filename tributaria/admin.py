from django.contrib import admin
from .models import ErrorValidacion
from .models import Notificacion
from .models import (
    Emisor,
    ArchivoTributario,
    CalificacionTributaria,
    ErrorValidacion,
    Bitacora,
    Notificacion,
)


@admin.register(Emisor)
class EmisorAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'rut', 'email_contacto')
    search_fields = ('nombre', 'rut')


@admin.register(ArchivoTributario)
class ArchivoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_original', 'tipo_archivo', 'usuario', 'estado', 'fecha_subida')
    list_filter = ('tipo_archivo', 'estado', 'fecha_subida')
    search_fields = ('nombre_original',)


@admin.register(CalificacionTributaria)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'emisor', 'corredor', 'anio_tributario', 'monto', 'factor', 'estado', 'fecha_registro')
    list_filter = ('anio_tributario', 'estado', 'emisor')
    search_fields = ('corredor', 'instrumento')


@admin.register(ErrorValidacion)
class ErrorValidacionAdmin(admin.ModelAdmin):
    list_display = ("archivo", "nro_linea", "mensaje", "fecha")
    list_filter = ("archivo", "fecha")
    search_fields = ("mensaje",)


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'usuario', 'accion', 'entidad', 'id_registro')
    list_filter = ('entidad', 'usuario')


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "mensaje", "nivel", "leida", "fecha")
    list_filter = ("nivel", "leida", "fecha")
    search_fields = ("mensaje", "usuario__username")
