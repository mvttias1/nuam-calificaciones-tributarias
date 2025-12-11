import os
import io
import pandas as pd
import re
from decimal import Decimal
from PyPDF2 import PdfReader

from .models import Calificacion
from django.db.models import Sum, Avg, Count
from .models import Notificacion
from django.db.models import Q
from django.utils import timezone
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.db.models import Sum, Count

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
from cuentas.decorators import rol_requerido


@login_required
def reporte_calificaciones(request):
    # Filtros del formulario
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    tipo_instrumento = request.GET.get("tipo_instrumento")
    tipo_renta = request.GET.get("tipo_renta")

    qs = Calificacion.objects.all()

    if desde:
        qs = qs.filter(fecha_registro__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)
    if tipo_instrumento:
        qs = qs.filter(tipo_instrumento=tipo_instrumento)
    if tipo_renta:
        qs = qs.filter(tipo_renta=tipo_renta)

    # Resumen global
    resumen = qs.aggregate(
        total_monto_bruto=Sum("monto_bruto"),
        total_monto_exento=Sum("monto_exento"),
        total_monto_afecto=Sum("monto_afecto"),
        total_monto_credito=Sum("monto_credito"),
        promedio_factor=Avg("factor"),
        cantidad=Count("id"),
    )

    context = {
        "calificaciones": qs[:200],  # para no reventar la tabla, máximo 200 filas
        "resumen": resumen,
        "filtros": {
            "desde": desde or "",
            "hasta": hasta or "",
            "tipo_instrumento": tipo_instrumento or "",
            "tipo_renta": tipo_renta or "",
        },
    }
    return render(request, "tributaria/reporte_calificaciones.html", context)


@login_required
def ver_notificaciones(request):
    # Base: todas las notificaciones ordenadas de la más nueva
    notificaciones = Notificacion.objects.all().order_by('-fecha_creacion')

    # --- FILTRO POR NIVEL (info, warning, error, etc.) ---
    nivel = request.GET.get('nivel')
    if nivel:
        notificaciones = notificaciones.filter(nivel=nivel)

    # --- FILTRO POR RANGO DE FECHAS ---
    desde = request.GET.get('desde')
    hasta = request.GET.get('hasta')

    if desde:
        notificaciones = notificaciones.filter(fecha_creacion__date__gte=desde)
    if hasta:
        notificaciones = notificaciones.filter(fecha_creacion__date__lte=hasta)

    # --- FILTRO POR USUARIO (para que corredor vea solo lo suyo, por ejemplo) ---
    # si tu modelo Notificacion tiene un campo 'usuario' lo puedes usar:
    if hasattr(Notificacion, 'usuario'):
        # Admin ve todo, el resto solo sus cosas (o globales si usuario es null)
        es_admin = getattr(request.user, 'is_superuser', False)
        if not es_admin:
            notificaciones = notificaciones.filter(
                Q(usuario=request.user) | Q(usuario__isnull=True)
            )

    context = {
        "notificaciones": notificaciones,
        "filtros": {
            "nivel": nivel or "",
            "desde": desde or "",
            "hasta": hasta or "",
        },
    }
    return render(request, "tributaria/notificaciones.html", context)


# -------------------------------------------
# Helper: convertir string de PDF a Decimal
# -------------------------------------------
def a_decimal(valor):
    """
    Convierte cosas como:
    - "3.200.000"  -> 3200000
    - "1,1"        -> 1.1
    - "110,00000"  -> 110.00000
    Devuelve Decimal o None.
    """
    if valor is None:
        return None

    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))

    s = str(valor).strip()
    if s == "":
        return None

    # quitamos separador de miles y normalizamos coma a punto
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        # Si no se puede convertir, devolvemos None y ya veremos el fallback
        return None





# ---------------------------------------------------
# FORMULARIO PARA SUBIR ARCHIVOS EXCEL / CSV
# ---------------------------------------------------
class ArchivoTributarioForm(forms.ModelForm):
    """Formulario para subir archivos tributarios (Excel/CSV)."""

    class Meta:
        model = ArchivoTributario
        fields = ["archivo"]


# ---------------------------------------------------
# FUNCIÓN AUXILIAR: REGISTRAR EN BITÁCORA
# ---------------------------------------------------
def registrar_bitacora(usuario, accion, entidad, id_registro=None, detalle=""):
    Bitacora.objects.create(
        usuario=usuario,
        accion=accion,
        entidad=entidad,
        id_registro=id_registro,
        detalle=detalle,
    )


# ---------------------------------------------------
# FUNCIÓN AUXILIAR: EXPORTAR CALIFICACIONES A EXCEL
# ---------------------------------------------------
def exportar_calificaciones_excel(qs):
    """
    Genera un archivo Excel con las calificaciones filtradas.
    Cumple con: CU4 (exportar resultados) y CU8 (reporte en Excel).
    """
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
    # Si te da error con openpyxl: pip install openpyxl
    with pd.ExcelWriter(buffer) as writer:
        df.to_excel(writer, sheet_name="Calificaciones", index=False)

    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = 'attachment; filename="calificaciones.xlsx"'
    return response


# ---------------------------------------------------
# PROCESAR ARCHIVO EXCEL / CSV
# ---------------------------------------------------
@transaction.atomic
def procesar_archivo_tributario(archivo_obj, usuario):
    ruta = archivo_obj.archivo.path
    extension = os.path.splitext(ruta)[1].lower()

    # ---------- CARGAR ARCHIVO SEGÚN EXTENSIÓN ----------
    try:
        if extension == ".csv":
            df = pd.read_csv(ruta)

        elif extension == ".xlsx":
            df = pd.read_excel(ruta, engine="openpyxl")

        elif extension == ".xls":
            df = pd.read_excel(ruta, engine="xlrd")

        else:
            raise Exception(f"Formato no soportado: {extension}")

    except Exception as e:
        raise Exception(
            f"No se pudo leer el archivo. Asegúrese que es CSV o Excel válido. Error: {e}"
        )

    print("COLUMNAS ENCONTRADAS:", list(df.columns))

    # ---------- NORMALIZAR NOMBRES ----------
    mapping = {}
    for col in df.columns:
        clave = col.strip().lower().replace(" ", "_")
        mapping[col] = clave

    df = df.rename(columns=mapping)

    # ---------- COLUMNAS REQUERIDAS ----------
    columnas_requeridas = [
        "rut_contribuyente",
        "nombre_contribuyente",
        "rut_emisor",
        "nombre_emisor",
        "monto_bruto",
        "factor",
        "anio_tributario",
    ]

    for col in columnas_requeridas:
        if col not in df.columns:
            raise Exception(
                f"Falta la columna '{col}'. Columnas encontradas: {list(df.columns)}"
            )

    registros_ok = 0
    registros_con_error = 0

    ErrorValidacion.objects.filter(archivo=archivo_obj).delete()

    for index, row in df.iterrows():
        nro_linea = index + 2
        errores = []

        # ---------- VALIDACIONES ----------
        for campo in [
            "rut_contribuyente",
            "nombre_contribuyente",
            "rut_emisor",
            "nombre_emisor",
        ]:
            if pd.isna(row[campo]) or str(row[campo]).strip() == "":
                errores.append(f"{campo} es obligatorio")

        # ---------- CONVERSIONES ----------
        try:
            monto = float(row["monto_bruto"])
            if monto <= 0:
                errores.append("monto_bruto debe ser mayor a 0")
        except Exception:
            errores.append("monto_bruto no es numérico")
            monto = None

        try:
            factor = float(row["factor"])
            if factor <= 0:
                errores.append("factor debe ser mayor a 0")
        except Exception:
            errores.append("factor no es numérico")
            factor = None

        try:
            anio = int(row["anio_tributario"])
            if anio < 2000 or anio > 2100:
                errores.append("año fuera de rango")
        except Exception:
            errores.append("anio_tributario inválido")
            anio = None

        # ---------- SI HAY ERRORES ----------
        if errores:
            registros_con_error += 1
            for e in errores:
                ErrorValidacion.objects.create(
                    archivo=archivo_obj,
                    nro_linea=nro_linea,
                    mensaje=e,
                )
            continue

        # ---------- CREAR EMISOR ----------
        emisor, _ = Emisor.objects.get_or_create(
            rut=str(row["rut_emisor"]).strip(),
            defaults={"nombre": str(row["nombre_emisor"]).strip()},
        )

        # ---------- CREAR CALIFICACIÓN ----------
        CalificacionTributaria.objects.create(
            emisor=emisor,
            anio_tributario=anio,
            monto=monto,
            factor=factor,
            monto_calificado=round(monto * factor, 2),
            corredor=usuario,
            estado="PENDIENTE",
            fuente="EXCEL",
        )

        registros_ok += 1

    return registros_ok, registros_con_error


# ---------------------------------------------------
# DASHBOARD (HU9 – Panel de control)
# ---------------------------------------------------
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


# ---------------------------------------------------
# SUBIR ARCHIVO (HU1 – Carga masiva Excel/CSV)
# ---------------------------------------------------
@login_required
@rol_requerido("Corredor", "Analista", "Administrador")
def subir_archivo(request):
    if request.method == "POST":
        form = ArchivoTributarioForm(request.POST, request.FILES)

        if form.is_valid():
            archivo = form.save(commit=False)
            extension = os.path.splitext(archivo.archivo.name)[1].lower()

            # ✅ Validación preventiva
            if extension not in [".csv", ".xlsx", ".xls"]:
                messages.error(
                    request,
                    "Formato no permitido. Solo se aceptan archivos CSV o Excel. "
                    "Para subir PDF use el módulo 'Subir PDF'.",
                )
                return redirect("subir_archivo")

            archivo.usuario = request.user
            archivo.save()

            registrar_bitacora(
                request.user,
                "Carga masiva de archivo",
                "ArchivoTributario",
                archivo.id,
            )

            try:
                ok, fail = procesar_archivo_tributario(archivo, request.user)

                nivel = "ERROR" if fail else "INFO"
                Notificacion.objects.create(
                    usuario=request.user,
                    mensaje=(
                        f"Archivo #{archivo.id} procesado. "
                        f"Registros OK: {ok}, con errores: {fail}."
                    ),
                    nivel=nivel,
                )

                messages.success(
                    request,
                    f"Archivo procesado correctamente. "
                    f"Registros OK: {ok} | Errores: {fail}",
                )

            except Exception as e:
                messages.error(request, f"Error al procesar archivo: {e}")
                return redirect("subir_archivo")

            return redirect("dashboard")
    else:
        form = ArchivoTributarioForm()

    return render(request, "tributaria/subir_archivo.html", {"form": form})


# ---------------------------------------------------
# LISTAR CALIFICACIONES (HU4 – búsquedas / filtros / export)
# ---------------------------------------------------
@login_required
@rol_requerido("Corredor", "Analista", "Administrador", "Auditor", "Gerente")
def listar_calificaciones(request):
    form = FiltroCalificacionForm(request.GET or None)
    calificaciones = CalificacionTributaria.objects.all()

    if form.is_valid():
        if form.cleaned_data.get("anio_tributario"):
            calificaciones = calificaciones.filter(
                anio_tributario=form.cleaned_data["anio_tributario"]
            )
        if form.cleaned_data.get("corredor"):
            calificaciones = calificaciones.filter(
                corredor__icontains=form.cleaned_data["corredor"]
            )
        if form.cleaned_data.get("emisor"):
            calificaciones = calificaciones.filter(
                emisor__nombre__icontains=form.cleaned_data["emisor"]
            )
        if form.cleaned_data.get("estado"):
            calificaciones = calificaciones.filter(
                estado=form.cleaned_data["estado"]
            )

    # ✅ Exportación a Excel de los resultados filtrados (CU4 + CU8)
    if request.GET.get("export") == "excel":
        return exportar_calificaciones_excel(calificaciones)

    return render(
        request,
        "tributaria/listar_calificaciones.html",
        {"form": form, "calificaciones": calificaciones},
    )


# ---------------------------------------------------
# CRUD CALIFICACIONES (HU3)
# ---------------------------------------------------
@login_required
@rol_requerido("Administrador", "Analista")
def crear_calificacion(request):
    if request.method == "POST":
        form = CalificacionForm(request.POST)
        if form.is_valid():
            calif = form.save(commit=False)
            calif.save()
            registrar_bitacora(
                request.user,
                "Crear calificación",
                "CalificacionTributaria",
                calif.id,
            )
            return redirect("listar_calificaciones")
    else:
        form = CalificacionForm()

    return render(
        request,
        "tributaria/editar_calificacion.html",
        {"form": form, "titulo": "Nueva Calificación"},
    )


@login_required
@rol_requerido("Administrador")
def editar_calificacion(request, pk):
    calif = get_object_or_404(CalificacionTributaria, pk=pk)
    if request.method == "POST":
        form = CalificacionForm(request.POST, instance=calif)
        if form.is_valid():
            form.save()
            registrar_bitacora(
                request.user,
                "Editar calificación",
                "CalificacionTributaria",
                calif.id,
            )
            return redirect("listar_calificaciones")
    else:
        form = CalificacionForm(instance=calif)

    return render(
        request,
        "tributaria/editar_calificacion.html",
        {"form": form, "titulo": "Editar Calificación"},
    )


@login_required
@rol_requerido("Administrador")
def eliminar_calificacion(request, pk):
    calif = get_object_or_404(CalificacionTributaria, pk=pk)
    if request.method == "POST":  # corregido: antes estaba POST__
        registrar_bitacora(
            request.user,
            "Eliminar calificación",
            "CalificacionTributaria",
            calif.id,
        )
        calif.delete()
        return redirect("listar_calificaciones")

    return render(
        request,
        "tributaria/confirmar_eliminar.html",
        {"calificacion": calif},
    )


# ---------------------------------------------------
# BITÁCORA (HU5 – auditoría)
# ---------------------------------------------------
@login_required
@rol_requerido("Administrador", "Auditor")
def ver_bitacora(request):
    registros = Bitacora.objects.order_by("-fecha")[:200]
    return render(request, "tributaria/ver_bitacora.html", {"registros": registros})


# ---------------------------------------------------
# ERRORES DE VALIDACIÓN (CU2 – ver detalle de reglas)
# ---------------------------------------------------
@login_required
@rol_requerido("Analista", "Administrador", "Auditor")
def errores_validacion(request, id_archivo=None):
    qs = ErrorValidacion.objects.select_related("archivo").order_by(
        "archivo_id", "nro_linea"
    )
    if id_archivo is not None:
        qs = qs.filter(archivo_id=id_archivo)

    return render(request, "tributaria/errores_validacion.html", {"errores": qs})


# ---------------------------------------------------
# REPORTE CONSOLIDADO (CU8 – totales por año)
# ---------------------------------------------------
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

    return render(
        request,
        "tributaria/reporte_consolidado.html",
        {"resumen_por_anio": resumen_por_anio},
    )


# ---------------------------------------------------
# NOTIFICACIONES (CU10 – listarlas)
# ---------------------------------------------------
@login_required
def listar_notificaciones(request):
    notifs = Notificacion.objects.filter(usuario=request.user).order_by("-fecha")
    return render(
        request,
        "tributaria/notificaciones.html",
        {"notificaciones": notifs},
    )


# ---------------------------------------------------
# HELPERS PARA PDF
# ---------------------------------------------------


def extraer_datos_desde_pdf(ruta_pdf):
    """
    Lee el PDF y trata de extraer:
    - RUT emisor
    - Nombre emisor
    - Año tributario
    - Monto bruto
    - Factor

    Está ajustado al formato de tu PDF interno que dice:
    RUT Emisor
    Nombre Emisor
    Año Tributario
    Monto Bruto
    Factor
    """
    reader = PdfReader(ruta_pdf)
    texto = "\n".join((page.extract_text() or "") for page in reader.pages)

    def buscar(patron):
        m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    datos = {}

    # Emisor
    datos["rut_emisor"] = buscar(r"RUT\s+Emisor\s+([\d\.\-Kk]+)")
    datos["nombre_emisor"] = buscar(r"Nombre\s+Emisor\s+([^\n]+)")

    # Año
    datos["anio_tributario"] = buscar(r"Año\s+Tributario\s+([0-9]{4})")

    # Monto bruto (ej: "Monto Bruto\n$3.200.000")
    datos["monto_bruto"] = buscar(r"Monto\s+Bruto\s+\$?([\d\.\,]+)")

    # Factor (ej: "Factor\n1,1" o "Factor\n1.1")
    datos["factor"] = buscar(r"Factor\s+([\d\.\,]+)")

    # Logs para que puedas ver en la consola de Django
    print("=== TEXTO PDF ===")
    print(texto)
    print("=== DATOS EXTRAÍDOS ===")
    print(datos)

    return datos


# ---------------------------------------------------
# SUBIR PDF Y CREAR CALIFICACIÓN
# ---------------------------------------------------


@login_required
def subir_pdf(request):
    if request.method == "POST":
        form = DocumentoPDFForm(request.POST, request.FILES)
        if form.is_valid():
            # 1) Guardar el PDF
            doc = form.save(commit=False)
            doc.usuario = request.user
            doc.save()

            ruta_pdf = doc.archivo.path

            # 2) Leer datos del PDF
            datos = extraer_datos_desde_pdf(ruta_pdf)

            # 3) Guardar lo que se pueda en DocumentoPDF
            doc.rut_emisor = datos.get("rut_emisor")
            doc.nombre_emisor = datos.get("nombre_emisor")

            doc.anio_tributario = (
                int(datos["anio_tributario"])
                if datos.get("anio_tributario")
                else None
            )

            doc.monto_bruto = a_decimal(datos.get("monto_bruto"))
            doc.factor = a_decimal(datos.get("factor"))

            if not doc.estado:
                doc.estado = "PENDIENTE"

            doc.save()

            # 4) Valores con fallback para la Calificación
            rut = doc.rut_emisor or "RUT_DESCONOCIDO"
            nombre_emisor = doc.nombre_emisor or "EMISOR DESCONOCIDO"
            anio = doc.anio_tributario or 2024

            # Si no se pudo leer, usamos 0 / 1
            monto = float(doc.monto_bruto) if doc.monto_bruto is not None else 0.0
            factor = float(doc.factor) if doc.factor is not None else 1.0
            estado = doc.estado or "PENDIENTE"

            print("=== VALORES PARA CALIFICACIÓN ===")
            print(
                dict(
                    rut=rut,
                    nombre_emisor=nombre_emisor,
                    anio=anio,
                    monto=monto,
                    factor=factor,
                    estado=estado,
                )
            )

            try:
                # 5) Crear / obtener emisor
                emisor, _ = Emisor.objects.get_or_create(
                    rut=rut,
                    defaults={"nombre": nombre_emisor},
                )

                # 6) Crear calificación
                calif = CalificacionTributaria.objects.create(
                    emisor=emisor,
                    corredor=request.user,
                    anio_tributario=anio,
                    monto=monto,
                    factor=factor,
                    monto_calificado=round(monto * factor, 2),
                    estado=estado,
                    fuente="PDF",
                )

                registrar_bitacora(
                    request.user,
                    "Crear calificación desde PDF",
                    "CalificacionTributaria",
                    calif.id,
                    detalle=(
                        f"PDF #{doc.id} | RUT={rut}, Año={anio}, "
                        f"Monto={monto}, Factor={factor}"
                    ),
                )

                messages.success(
                    request,
                    f"PDF subido y calificación #{calif.id} creada "
                    f"para {nombre_emisor} ({rut}), año {anio}.",
                )

            except Exception as e:
                # Si algo falla al crear la calificación, al menos queda el PDF
                messages.error(
                    request,
                    f"PDF guardado, pero falló la creación de la calificación: {e}",
                )
                print("ERROR CREANDO CALIFICACIÓN DESDE PDF:", e)

            return redirect("dashboard")

    else:
        form = DocumentoPDFForm()

    return render(request, "tributaria/subir_pdf.html", {"form": form})


# ---------------------------------------------------
# LISTAR PDFs SUBIDOS
# ---------------------------------------------------
@login_required
def listar_pdfs(request):
    docs = DocumentoPDF.objects.filter(usuario=request.user).order_by("-fecha_subida")
    return render(request, "tributaria/listar_pdfs.html", {"docs": docs})
