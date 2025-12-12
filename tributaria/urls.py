from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("subir-archivo/", views.subir_archivo, name="subir_archivo"),

    # Calificaciones
    path("calificaciones/nueva/", views.crear_calificacion, name="crear_calificacion"),
    path("calificaciones/", views.listar_calificaciones, name="listar_calificaciones"),
    path("calificaciones/<int:pk>/editar/", views.editar_calificacion, name="editar_calificacion"),
    path("calificaciones/<int:pk>/eliminar/", views.eliminar_calificacion, name="eliminar_calificacion"),

    # Errores de validación
    path("errores-validacion/", views.errores_validacion, name="errores_validacion"),
    path("errores-validacion/<int:id_archivo>/", views.errores_validacion, name="errores_validacion_por_archivo"),

    # Bitácora
    path("bitacora/", views.ver_bitacora, name="ver_bitacora"),

    # Notificaciones
    path("notificaciones/", views.ver_notificaciones, name="ver_notificaciones"),

    # Reportes
    path("reportes/", views.reporte_calificaciones, name="reporte_calificaciones"),
    path("reportes/consolidado/", views.reporte_consolidado, name="reporte_consolidado"),
    path(
        "reportes/informe-gestion/",
        views.informe_gestion_pdf,
        name="informe_gestion_pdf",
    ),

    # Auth
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # PDF
    path("subir-pdf/", views.subir_pdf, name="subir_pdf"),
    path("pdfs/", views.listar_pdfs, name="listar_pdfs"),
]
