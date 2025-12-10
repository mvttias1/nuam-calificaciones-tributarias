from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("subir-archivo/", views.subir_archivo, name="subir_archivo"),
    path("calificaciones/nueva/", views.crear_calificacion, name="crear_calificacion"),
    path("calificaciones/", views.listar_calificaciones, name="listar_calificaciones"),
    path("calificaciones/<int:pk>/editar/", views.editar_calificacion, name="editar_calificacion"),
    path("errores-validacion/<int:id_archivo>/", views.errores_validacion, name="errores_validacion_archivo"), 
    path("calificaciones/<int:pk>/eliminar/", views.eliminar_calificacion, name="eliminar_calificacion"),
    path("calificaciones/nueva/", views.crear_calificacion, name="crear_calificacion",),
    path(
        "calificaciones/<int:pk>/editar/",
        views.editar_calificacion,
        name="editar_calificacion",
    ),
    path(
        "calificaciones/<int:pk>/eliminar/",
        views.eliminar_calificacion,
        name="eliminar_calificacion",
    ),
    path("bitacora/", views.ver_bitacora, name="ver_bitacora"),
    path("errores-validacion/", views.errores_validacion, name="errores_validacion"),
    path("errores-validacion/<int:id_archivo>/", views.errores_validacion, name="errores_validacion_por_archivo"),
    path('errores/', views.errores_validacion, name='errores_validacion'),
    path("reportes/consolidado/", views.reporte_consolidado, name="reporte_consolidado"),
    path("notificaciones/", views.listar_notificaciones, name="notificaciones"),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path("subir-pdf/", views.subir_pdf, name="subir_pdf"),
    path("pdfs/", views.listar_pdfs, name="listar_pdfs"),


]
