import os
import io
import re
import pandas as pd
from decimal import Decimal
from PyPDF2 import PdfReader

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import get_template
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone

from cuentas.models import Usuario, Rol

# ---------------------------------------------------
# Import seguro de decorators (para evitar que runserver muera si faltan)
# ---------------------------------------------------
try:
    from cuentas.decorators import solo_admin, rol_requerido
except Exception:
    # Fallback simple (no rompe el proyecto si se borró decoradores.py por accidente)
    def solo_admin(view_func):
        @login_required
        def _wrapped(request, *args, **kwargs):
            u = request.user
            if getattr(u, "is_superuser", False) or (getattr(u, "rol", None) and u.rol.nombre == "Administrador"):
                return view_func(request, *args, **kwargs)
            messages.error(request, "No tienes permisos para acceder aquí.")
            return redirect("dashboard")
        return _wrapped

    def rol_requerido(*roles):
        def decorator(view_func):
            @login_required
            def _wrapped(request, *args, **kwargs):
                u = request.user
                user_rol = getattr(getattr(u, "rol", None), "nombre", None)
                if getattr(u, "is_superuser", False) or (user_rol in roles):
                    return view_func(request, *args, **kwargs)
                messages.error(request, "No tienes permisos para acceder aquí.")
                return redirect("dashboard")
            return _wrapped
        return decorator


# ---------------------------------------------------
# Import seguro de xhtml2pdf (Render fallaba por ModuleNotFoundError)
# ---------------------------------------------------
try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None

from .forms import DocumentoPDFForm, CalificacionForm, FiltroCalificacionForm
from .models import (
    ArchivoTributario,
    CalificacionTributaria,
    Bitacora,
    Emisor,
    ErrorValidacion,
    Notificacion,
    DocumentoPDF,
)


# ===================================================
# Helpers
# ===================================================

def a_decimal(valor):
    """
    Convierte strings tipo:
    - "3.200.000" -> 3200000
    - "110,00000" -> 110.00000
    Devuelve Decimal o None.
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))

    s = str(valor).strip()
    if s == "":
        return None

    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None


def registrar_bitacora(usuario, accion, entidad, id_registro=None, detalle=""):
    Bitacora.objects.create(
        usuario=usuario,
        accion=accion,
        entidad=entidad,
        id_registro=id_registro,
        detalle=detalle,
    )


def notificar(usuario, mensaje, nivel="INFO"):
    Notificacion.objects.create(usuario=usuario, mensaje=mensaje, nivel=nivel)


# ===================================================
# Formularios
# ===================================================

class ArchivoTributarioForm(forms.ModelForm):
    class Meta:
        model = ArchivoTributario
        fields = ["archivo"]


# ===================================================
# Reporte PDF Gestión (Admin)
# ===================================================

@login_required
@solo_admin
def informe_gestion_pdf(request):
    if pisa is None:
        messages.error(request, "Falta instalar xhtml2pdf para generar PDFs en el servidor.")
        return redirect("dashboard")

    template = get_template("reportes/informe_gestion.html")

    # Conteos/estadísticas (ajusta estados si tus choices son distintos)
    qs = CalificacionTributaria.objects.all()
    context = {
        "usuarios_total": Usuario.objects.count(),
        "usuarios_por_rol": Rol.objects.all(),
        "calificaciones_total": qs.count(),
        "monto_total": qs.aggregate(total=Sum("monto")).get("total") or 0,
        "pendientes": qs.filter(estado="PENDIENTE").count(),
        "validadas": qs.filter(estado="VALIDADA").count(),
        "archivos": ArchivoTributario.objects.count(),
        "pdfs": DocumentoPDF.objects.count(),
        "usuario": request.user,
        "fecha": timezone.now(),
    }

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="informe_gestion_nuam.pdf"'
    pisa.CreatePDF(template.render(context), dest=response)
    return response


# ===================================================
# Reporte calificaciones (pantalla)
# ===================================================

@login_required
def reporte_calificaciones(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    tipo_instrumento = request.GET.get("tipo_instrumento")
    tipo_renta = request.GET.get("tipo_renta")

    qs = CalificacionTributaria.objects.all()

    if desde:
        qs = qs.filter(fecha_registro__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)

    # ⚠️ estos campos dependen de tu modelo real (instrumento__tipo / tipo_renta)
    if tipo_instrumento:
        qs = qs.filter(instrumento__icontains=tipo_instrumento)
    if tipo_renta:
        qs = qs.filter(tipo_renta__icontains=tipo_renta)

    resumen = qs.aggregate(
        total_monto=Sum("monto"),
        total_monto_calificado=Sum("monto_calificado"),
        promedio_factor=Avg("factor"),
        cantidad=Count("id"),
    )

    context = {
        "calificaciones": qs[:200],
        "resumen": resumen,
        "filtros": {
            "desde": desde or "",
            "hasta": hasta or "",
            "tipo_instrumento": tipo_instrumento or "",
            "tipo_renta": tipo_renta or "",
        },
    }
    return render(request, "tributaria/reporte_calificaciones.html", context)


# ===================================================
# Notificaciones
# ===================================================

@login_required
def ver_notificaciones(request):
    notificaciones = Notificacion.objects.all().order_by("-fecha")

    nivel = request.GET.get("nivel")
    if nivel:
        notificaciones = notificaciones.filter(nivel=nivel)

    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    if desde:
        notificaciones = notificaciones.filter(fecha__date__gte=desde)
    if hasta:
        notificaciones = notificaciones.filter(fecha__date__lte=hasta)

    # Si no es admin, solo ve las suyas
    if not getattr(request.user, "is_superuser", False):
        notificaciones = notificaciones.filter(Q(usuario=request.user) | Q(usuario__isnull=True))

    return render(
        request,
        "tributaria/notificaciones.html",
        {"notificaciones": notificaciones, "filtros": {"nivel": nivel or "", "desde": desde or "", "hasta": hasta or ""}},
    )


# ===================================================
# Exportar Excel
# ===================================================

def exportar_calificaciones_excel(qs):
    filas = []
    for c in qs.select_related("emisor"):
        filas.append(
            {
                "ID": c.id,
                "Emisor": str(c.emisor) if c.emisor else "",
                "Corredor": str(c.corredor),
                "Año tributario": c.anio_tributario,
                "Monto": float(c.monto),
                "Factor": float(c.factor),
                "Monto calificado": float(c.monto_calificado),
                "Estado": c.estado,
                "Fuente": getattr(c, "fuente", ""),
            }
        )

    df = pd.DataFrame(filas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        df.to_excel(writer, sheet_name="Calificaciones", index=False)

    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="calificaciones.xlsx"'
    return response


# ===================================================
# Procesar Excel/CSV (lo importante: NO crear calificaciones si el archivo no corresponde)
# ===================================================

EXT_PERMITIDAS = {".csv", ".xlsx", ".xls"}

# Columnas obligatorias del formato NUAM esperado
COLUMNAS_REQUERIDAS = {
    "rut_contribuyente",
    "nombre_contribuyente",
    "rut_emisor",
    "nombre_emisor",
    "monto_bruto",
    "factor",
    "anio_tributario",
}

def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        clave = str(col).strip().lower().replace(" ", "_")
        mapping[col] = clave
    return df.rename(columns=mapping)


@transaction.atomic
def procesar_archivo_tributario(archivo_obj, usuario):
    """
    Retorna: (ok:int, fail:int, archivo_valido:bool)
    - archivo_valido=False significa: el archivo NO corresponde al formato esperado (por columnas)
    - en ese caso NO se crean calificaciones.
    """
    ruta = archivo_obj.archivo.path
    extension = os.path.splitext(ruta)[1].lower()

    # 1) Leer archivo
    try:
        if extension == ".csv":
            df = pd.read_csv(ruta)
        elif extension == ".xlsx":
            df = pd.read_excel(ruta, engine="openpyxl")
        elif extension == ".xls":
            df = pd.read_excel(ruta)  # xlrd solo si está instalado
        else:
            # no debería llegar por validación previa
            raise Exception(f"Formato no soportado: {extension}")
    except Exception as e:
        raise Exception(f"No se pudo leer el archivo. Error: {e}")

    df = _normalizar_columnas(df)

    # 2) Validar columnas (SI FALLA -> archivo inválido, registrar ErrorValidacion y salir sin crear calificaciones)
    faltantes = sorted(list(COLUMNAS_REQUERIDAS - set(df.columns)))
    if faltantes:
        ErrorValidacion.objects.filter(archivo=archivo_obj).delete()
        ErrorValidacion.objects.create(
            archivo=archivo_obj,
            nro_linea=1,
            mensaje=f"Archivo inválido: faltan columnas obligatorias: {', '.join(faltantes)}",
        )
        return 0, 0, False

    # 3) Procesar filas (aquí sí se crean calificaciones SOLO para filas válidas)
    ok = 0
    fail = 0

    ErrorValidacion.objects.filter(archivo=archivo_obj).delete()

    for index, row in df.iterrows():
        nro_linea = index + 2
        errores = []

        # obligatorios texto
        for campo in ["rut_contribuyente", "nombre_contribuyente", "rut_emisor", "nombre_emisor"]:
            if pd.isna(row.get(campo)) or str(row.get(campo)).strip() == "":
                errores.append(f"{campo} es obligatorio")

        # monto
        monto = None
        try:
            monto = float(row.get("monto_bruto"))
            if monto <= 0:
                errores.append("monto_bruto debe ser mayor a 0")
        except Exception:
            errores.append("monto_bruto no es numérico")

        # factor
        factor = None
        try:
            factor = float(row.get("factor"))
            if factor <= 0:
                errores.append("factor debe ser mayor a 0")
        except Exception:
            errores.append("factor no es numérico")

        # año
        anio = None
        try:
            anio = int(row.get("anio_tributario"))
            if anio < 2000 or anio > 2100:
                errores.append("anio_tributario fuera de rango (2000-2100)")
        except Exception:
            errores.append("anio_tributario inválido")

        if errores:
            fail += 1
            for e in errores:
                ErrorValidacion.objects.create(archivo=archivo_obj, nro_linea=nro_linea, mensaje=e)
            continue

        # Emisor
        emisor, _ = Emisor.objects.get_or_create(
            rut=str(row.get("rut_emisor")).strip(),
            defaults={"nombre": str(row.get("nombre_emisor")).strip()},
        )

        # IMPORTANTE: tu modelo tiene corredor como CharField, así que guardamos username
        corredor_txt = getattr(usuario, "username", str(usuario))

        CalificacionTributaria.objects.create(
            emisor=emisor,
            anio_tributario=anio,
            monto=monto,
            factor=factor,
            monto_calificado=round(monto * factor, 2),
            corredor=corredor_txt,
            estado="PENDIENTE",
            fuente="EXCEL/CSV",
        )

        ok += 1

    return ok, fail, True


# ===================================================
# Dashboard
# ===================================================

@login_required
@rol_requerido("Gerente", "Administrador")
def dashboard(request):
    context = {
        "total_calificaciones": CalificacionTributaria.objects.count(),
        "total_archivos": ArchivoTributario.objects.count(),
        "total_pdfs": DocumentoPDF.objects.count(),
        "total_errores": ErrorValidacion.objects.count(),
        "ultimas_acciones": Bitacora.objects.order_by("-fecha")[:8],
    }
    return render(request, "tributaria/dashboard.html", context)


# ===================================================
# Subir archivo Excel/CSV
# ===================================================

@login_required
@rol_requerido("Corredor", "Analista", "Administrador")
def subir_archivo(request):
    if request.method == "POST":
        form = ArchivoTributarioForm(request.POST, request.FILES)
        if form.is_valid():
            archivo_obj = form.save(commit=False)
            extension = os.path.splitext(archivo_obj.archivo.name)[1].lower()

            if extension not in EXT_PERMITIDAS:
                messages.error(
                    request,
                    "Formato no permitido. Solo CSV/Excel. Para PDF usa 'Subir PDF'.",
                )
                return redirect("subir_archivo")

            archivo_obj.usuario = request.user
            archivo_obj.estado = "PENDIENTE"
            archivo_obj.nombre_original = archivo_obj.archivo.name
            archivo_obj.save()

            registrar_bitacora(request.user, "Carga masiva de archivo", "ArchivoTributario", archivo_obj.id)

            try:
                ok, fail, valido = procesar_archivo_tributario(archivo_obj, request.user)

                if not valido:
                    # Archivo no corresponde al formato: NO se crean calificaciones
                    archivo_obj.estado = "CON_ERRORES"
                    archivo_obj.mensaje_estado = "Archivo no corresponde al formato esperado (columnas inválidas)."
                    archivo_obj.save(update_fields=["estado", "mensaje_estado"])

                    notificar(
                        request.user,
                        f"Archivo #{archivo_obj.id} rechazado: columnas inválidas. Revisa Errores de validación.",
                        nivel="ERROR",
                    )
                    messages.error(request, "El archivo NO corresponde al formato NUAM esperado. No se registró nada.")
                    return redirect("errores_validacion", id_archivo=archivo_obj.id)

                # Válido pero con filas erróneas
                if fail > 0:
                    archivo_obj.estado = "CON_ERRORES"
                    archivo_obj.mensaje_estado = f"Procesado con errores. OK={ok}, errores={fail}."
                    archivo_obj.save(update_fields=["estado", "mensaje_estado"])
                    notificar(request.user, f"Archivo #{archivo_obj.id} procesado con errores. OK={ok}, errores={fail}.", nivel="WARNING")
                    messages.warning(request, f"Archivo procesado con errores. OK={ok} | Errores={fail}")
                    return redirect("errores_validacion", id_archivo=archivo_obj.id)

                # Todo OK
                archivo_obj.estado = "PROCESADO"
                archivo_obj.mensaje_estado = f"Procesado correctamente. OK={ok}."
                archivo_obj.save(update_fields=["estado", "mensaje_estado"])
                notificar(request.user, f"Archivo #{archivo_obj.id} procesado OK. Registros={ok}.", nivel="INFO")
                messages.success(request, f"Archivo procesado correctamente. Registros OK: {ok}")
                return redirect("dashboard")

            except Exception as e:
                archivo_obj.estado = "CON_ERRORES"
                archivo_obj.mensaje_estado = f"Error leyendo/procesando archivo: {e}"
                archivo_obj.save(update_fields=["estado", "mensaje_estado"])
                notificar(request.user, f"Archivo #{archivo_obj.id} falló al procesar: {e}", nivel="ERROR")
                messages.error(request, f"Error al procesar archivo: {e}")
                return redirect("subir_archivo")
    else:
        form = ArchivoTributarioForm()

    return render(request, "tributaria/subir_archivo.html", {"form": form})


# ===================================================
# Listar calificaciones + filtros + export
# ===================================================

@login_required
@rol_requerido("Corredor", "Analista", "Administrador", "Auditor", "Gerente")
def listar_calificaciones(request):
    form = FiltroCalificacionForm(request.GET or None)
    calificaciones = CalificacionTributaria.objects.all()

    if form.is_valid():
        if form.cleaned_data.get("anio_tributario"):
            calificaciones = calificaciones.filter(anio_tributario=form.cleaned_data["anio_tributario"])
        if form.cleaned_data.get("corredor"):
            calificaciones = calificaciones.filter(corredor__icontains=form.cleaned_data["corredor"])
        if form.cleaned_data.get("emisor"):
            calificaciones = calificaciones.filter(emisor__nombre__icontains=form.cleaned_data["emisor"])
        if form.cleaned_data.get("estado"):
            calificaciones = calificaciones.filter(estado=form.cleaned_data["estado"])

    if request.GET.get("export") == "excel":
        return exportar_calificaciones_excel(calificaciones)

    return render(request, "tributaria/listar_calificaciones.html", {"form": form, "calificaciones": calificaciones})


# ===================================================
# CRUD calificaciones
# ===================================================

@login_required
@rol_requerido("Administrador", "Analista")
def crear_calificacion(request):
    if request.method == "POST":
        form = CalificacionForm(request.POST)
        if form.is_valid():
            calif = form.save()
            registrar_bitacora(request.user, "Crear calificación", "CalificacionTributaria", calif.id)
            return redirect("listar_calificaciones")
    else:
        form = CalificacionForm()

    return render(request, "tributaria/editar_calificacion.html", {"form": form, "titulo": "Nueva Calificación"})


@login_required
@rol_requerido("Administrador")
def editar_calificacion(request, pk):
    calif = get_object_or_404(CalificacionTributaria, pk=pk)
    if request.method == "POST":
        form = CalificacionForm(request.POST, instance=calif)
        if form.is_valid():
            form.save()
            registrar_bitacora(request.user, "Editar calificación", "CalificacionTributaria", calif.id)
            return redirect("listar_calificaciones")
    else:
        form = CalificacionForm(instance=calif)

    return render(request, "tributaria/editar_calificacion.html", {"form": form, "titulo": "Editar Calificación"})


@login_required
@rol_requerido("Administrador")
def eliminar_calificacion(request, pk):
    calif = get_object_or_404(CalificacionTributaria, pk=pk)
    if request.method == "POST":
        registrar_bitacora(request.user, "Eliminar calificación", "CalificacionTributaria", calif.id)
        calif.delete()
        return redirect("listar_calificaciones")

    return render(request, "tributaria/confirmar_eliminar.html", {"calificacion": calif})


# ===================================================
# Bitácora
# ===================================================

@login_required
@rol_requerido("Administrador", "Auditor")
def ver_bitacora(request):
    registros = Bitacora.objects.order_by("-fecha")[:200]
    return render(request, "tributaria/ver_bitacora.html", {"registros": registros})


# ===================================================
# Errores validación
# ===================================================

@login_required
@rol_requerido("Analista", "Administrador", "Auditor")
def errores_validacion(request, id_archivo=None):
    qs = ErrorValidacion.objects.select_related("archivo").order_by("archivo_id", "nro_linea")
    if id_archivo is not None:
        qs = qs.filter(archivo_id=id_archivo)

    return render(request, "tributaria/errores_validacion.html", {"errores": qs})


# ===================================================
# Reporte consolidado
# ===================================================

@login_required
@rol_requerido("Gerente", "Administrador", "Auditor")
def reporte_consolidado(request):
    resumen_por_anio = (
        CalificacionTributaria.objects.values("anio_tributario")
        .annotate(
            cantidad=Count("id"),
            total_monto=Sum("monto"),
            total_monto_calificado=Sum("monto_calificado"),
        )
        .order_by("anio_tributario")
    )
    return render(request, "tributaria/reporte_consolidado.html", {"resumen_por_anio": resumen_por_anio})


# ===================================================
# PDF: extracción y subida (IMPORTANTE: no crear calificación si faltan datos)
# ===================================================

def extraer_datos_desde_pdf(ruta_pdf):
    reader = PdfReader(ruta_pdf)
    texto = "\n".join((page.extract_text() or "") for page in reader.pages)

    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    datos = {
        "rut_emisor": buscar(r"RUT\s+Emisor\s+([\d\.\-Kk]+)"),
        "nombre_emisor": buscar(r"Nombre\s+Emisor\s+([^\n]+)"),
        "anio_tributario": buscar(r"Año\s+Tributario\s+([0-9]{4})"),
        "monto_bruto": buscar(r"Monto\s+Bruto\s+\$?([\d\.\,]+)"),
        "factor": buscar(r"Factor\s+([\d\.\,]+)"),
    }
    return datos


@login_required
@rol_requerido("Corredor", "Analista", "Administrador")
def subir_pdf(request):
    if request.method == "POST":
        form = DocumentoPDFForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.usuario = request.user
            doc.estado = doc.estado or "PENDIENTE"
            doc.save()

            ruta_pdf = doc.archivo.path
            datos = extraer_datos_desde_pdf(ruta_pdf)

            doc.rut_emisor = datos.get("rut_emisor")
            doc.nombre_emisor = datos.get("nombre_emisor")
            doc.anio_tributario = int(datos["anio_tributario"]) if datos.get("anio_tributario") else None
            doc.monto_bruto = a_decimal(datos.get("monto_bruto"))
            doc.factor = a_decimal(datos.get("factor"))
            doc.save()

            # ✅ VALIDACIÓN MÍNIMA: si falta algo crítico, NO crear calificación
            faltantes = []
            if not doc.rut_emisor:
                faltantes.append("rut_emisor")
            if not doc.nombre_emisor:
                faltantes.append("nombre_emisor")
            if doc.anio_tributario is None:
                faltantes.append("anio_tributario")
            if doc.monto_bruto is None or doc.monto_bruto <= 0:
                faltantes.append("monto_bruto")
            if doc.factor is None or doc.factor <= 0:
                faltantes.append("factor")

            if faltantes:
                doc.estado = "CON_ERRORES"
                doc.save(update_fields=["estado"])
                notificar(
                    request.user,
                    f"PDF #{doc.id} subido pero rechazado (faltan datos: {', '.join(faltantes)}). No se creó calificación.",
                    nivel="ERROR",
                )
                messages.error(
                    request,
                    "PDF subido, pero NO se creó calificación porque el PDF no trae datos válidos "
                    f"({', '.join(faltantes)}).",
                )
                return redirect("dashboard")

            # Crear emisor + calificación
            emisor, _ = Emisor.objects.get_or_create(
                rut=doc.rut_emisor,
                defaults={"nombre": doc.nombre_emisor},
            )

            corredor_txt = getattr(request.user, "username", str(request.user))
            monto = float(doc.monto_bruto)
            factor = float(doc.factor)

            calif = CalificacionTributaria.objects.create(
                emisor=emisor,
                corredor=corredor_txt,
                anio_tributario=doc.anio_tributario,
                monto=monto,
                factor=factor,
                monto_calificado=round(monto * factor, 2),
                estado="PENDIENTE",
                fuente="PDF",
            )

            registrar_bitacora(
                request.user,
                "Crear calificación desde PDF",
                "CalificacionTributaria",
                calif.id,
                detalle=f"PDF #{doc.id} | RUT={doc.rut_emisor}, Año={doc.anio_tributario}, Monto={monto}, Factor={factor}",
            )

            notificar(request.user, f"PDF #{doc.id} procesado OK. Calificación #{calif.id} creada.", nivel="INFO")
            messages.success(request, f"PDF subido y calificación #{calif.id} creada.")
            return redirect("dashboard")
    else:
        form = DocumentoPDFForm()

    return render(request, "tributaria/subir_pdf.html", {"form": form})


@login_required
def listar_pdfs(request):
    docs = DocumentoPDF.objects.filter(usuario=request.user).order_by("-fecha_subida")
    return render(request, "tributaria/listar_pdfs.html", {"docs": docs})
