from django.db import models
from django.conf import settings


Usuario = settings.AUTH_USER_MODEL


class Emisor(models.Model):
    """
    Empresa o entidad que emite información (certificados, DJ, etc.).
    Relacionado con HU1, HU7.
    """
    nombre = models.CharField(max_length=150)
    rut = models.CharField(max_length=20)
    email_contacto = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.rut})"


class ArchivoTributario(models.Model):
    """
    Archivo subido para carga masiva (HU1 y HU7).
    """
    TIPO_ARCHIVO_CHOICES = [
        ('CSV', 'CSV'),
        ('XLSX', 'Excel'),
        ('XML', 'XML'),
        ('PDF', 'PDF (certificado)'),
    ]

    tipo_archivo = models.CharField(max_length=10, choices=TIPO_ARCHIVO_CHOICES)
    archivo = models.FileField(upload_to='archivos_tributarios/')
    nombre_original = models.CharField(max_length=255)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    emisor = models.ForeignKey(Emisor, on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=20, default='PENDIENTE')  # PENDIENTE, PROCESADO, CON_ERRORES
    mensaje_estado = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nombre_original} ({self.tipo_archivo})"


class CalificacionTributaria(models.Model):
    """
    Calificación tributaria calculada (HU2, HU3, HU4).
    """
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('VALIDADA', 'Validada'),
        ('PUBLICADA', 'Publicada'),
    ]

    archivo_origen = models.ForeignKey(ArchivoTributario, on_delete=models.SET_NULL, null=True, blank=True)
    emisor = models.ForeignKey(Emisor, on_delete=models.PROTECT)
    corredor = models.CharField(max_length=100)  # simplificado, luego se puede relacionar con usuario
    instrumento = models.CharField(max_length=100, blank=True)
    anio_tributario = models.IntegerField()
    monto = models.DecimalField(max_digits=15, decimal_places=2)
    factor = models.DecimalField(max_digits=10, decimal_places=5)
    monto_calificado = models.DecimalField(max_digits=15, decimal_places=2)
    fuente = models.CharField(max_length=50, help_text="Por ejemplo: DJ, Certificado Emisor")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='BORRADOR')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    usuario_responsable = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Calif {self.id} - {self.emisor} - {self.anio_tributario}"




class Bitacora(models.Model):
    """
    Registro de acciones (HU5).
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=255)
    entidad = models.CharField(max_length=100)
    id_registro = models.IntegerField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    detalle = models.TextField(blank=True)

    def __str__(self):
        return f"[{self.fecha}] {self.usuario} - {self.accion}"


class Notificacion(models.Model):
    NIVEL_CHOICES = [
        ("INFO", "Información"),
        ("WARNING", "Advertencia"),
        ("ERROR", "Error"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
    )
    mensaje = models.CharField(max_length=255)
    nivel = models.CharField(max_length=10, choices=NIVEL_CHOICES, default="INFO")
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.mensaje[:40]}"

class ErrorValidacion(models.Model):
    """
    Guarda errores de validación detectados al procesar un archivo tributario.
    Cada registro representa un problema en una fila específica del archivo.
    """
    archivo = models.ForeignKey(
        "ArchivoTributario",
        on_delete=models.CASCADE,
        related_name="errores_validacion",
    )
    # en muchos casos no tendrás calificación creada si hubo error, por eso es opcional
    calificacion = models.ForeignKey(
        "CalificacionTributaria",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="errores_validacion",
    )
    nro_linea = models.IntegerField()   # número de fila en el Excel (considerando cabecera)
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Error de validación"
        verbose_name_plural = "Errores de validación"

    def __str__(self):
        return f"Archivo {self.archivo_id} - Fila {self.nro_linea}: {self.mensaje[:50]}"

class DocumentoPDF(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documentos_pdf",
    )
    nombre = models.CharField(max_length=200)
    archivo = models.FileField(upload_to="pdfs/")
    fecha_subida = models.DateTimeField(auto_now_add=True)

    # Campos que llenará automáticamente el parser del PDF
    rut_emisor = models.CharField(max_length=20, blank=True, null=True)
    nombre_emisor = models.CharField(max_length=200, blank=True, null=True)
    anio_tributario = models.IntegerField(blank=True, null=True)
    monto_bruto = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    factor = models.DecimalField(
        max_digits=10, decimal_places=5, blank=True, null=True
    )
    estado = models.CharField(
        max_length=20, default="PENDIENTE", blank=True, null=True
    )

    def __str__(self):
        return f"{self.nombre} ({self.rut_emisor or 'sin RUT'})"