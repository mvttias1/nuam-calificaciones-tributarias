from django import forms
from .models import ArchivoTributario, CalificacionTributaria, DocumentoPDF


# ────────────────────────────────
# Formulario para subir archivos Excel / CSV
# ────────────────────────────────
class ArchivoTributarioForm(forms.ModelForm):
    class Meta:
        model = ArchivoTributario
        fields = ["archivo"]


# ────────────────────────────────
# Formulario para crear / editar calificaciones
# ────────────────────────────────
class CalificacionForm(forms.ModelForm):
    class Meta:
        model = CalificacionTributaria
        fields = "__all__"


# ────────────────────────────────
# Formulario de filtros
# ────────────────────────────────
class FiltroCalificacionForm(forms.Form):
    anio_tributario = forms.IntegerField(required=False, label="Año")
    corredor = forms.CharField(required=False, label="Corredor")
    emisor = forms.CharField(required=False, label="Emisor")
    estado = forms.CharField(required=False, label="Estado")


# ────────────────────────────────
# Formulario genérico de subida (por si se usa)
# ────────────────────────────────
class ArchivoUploadForm(forms.Form):
    archivo = forms.FileField(label="Archivo")


# ────────────────────────────────
# Formulario para subir PDF
# ────────────────────────────────
class DocumentoPDFForm(forms.ModelForm):
    class Meta:
        model = DocumentoPDF
        fields = ["nombre", "archivo"]
