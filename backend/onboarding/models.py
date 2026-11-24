"""
Documentos recibidos y campos extraídos.

El archivo de cada documento se guarda CIFRADO en disco (MEDIA_ROOT) y acá solo queda su ruta y
su huella SHA-256 del original: si alguien cambiara el archivo, la huella no coincidiría.
"""

import uuid

from django.conf import settings
from django.db import models

from creditos.models import Solicitud
from nucleo.cifrado import CampoCifrado


class TipoDocumento(models.TextChoices):
    CI_FRENTE = "ci_frente", "Cédula (frente)"
    CI_DORSO = "ci_dorso", "Cédula (dorso)"
    SELFIE = "selfie", "Selfie"
    LIQUIDACION = "liquidacion", "Liquidación de sueldo"
    EXTRACTO_IPS = "extracto_ips", "Extracto de IPS"


class EstadoDocumento(models.TextChoices):
    RECIBIDO = "recibido", "Recibido"
    PROCESANDO = "procesando", "Leyendo"
    LEGIBLE = "legible", "Legible"
    ILEGIBLE = "ilegible", "Ilegible"
    ERROR = "error", "Error al procesar"


class Documento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, related_name="documentos")
    tipo = models.CharField(max_length=20, choices=TipoDocumento.choices)
    archivo = models.CharField(max_length=300)          # ruta del archivo CIFRADO dentro de MEDIA_ROOT
    sha256 = models.CharField(max_length=64)            # huella del archivo ORIGINAL (sin cifrar)
    tipo_mime = models.CharField(max_length=40)
    tamanio_bytes = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, choices=EstadoDocumento.choices, default=EstadoDocumento.RECIBIDO)
    # Si el cliente manda de nuevo el mismo tipo, el anterior queda "reemplazado" (no se borra: trazabilidad).
    reemplazado = models.BooleanField(default=False)

    confianza_global = models.FloatField(null=True, blank=True)   # promedio de confianza del OCR (0 a 1)
    texto_ocr = CampoCifrado(blank=True)                          # texto leído: tiene datos personales → cifrado
    motivo = models.CharField(max_length=200, blank=True)         # por qué es ilegible o falló
    verificacion_facial = models.JSONField(default=dict, blank=True)   # solo selfie; dice si es simulada

    recibido = models.DateTimeField(auto_now_add=True)
    # Cuándo lo tomó un worker. Si un worker se cae a mitad, pasado un rato otro puede retomarlo.
    en_proceso_desde = models.DateTimeField(null=True, blank=True)
    procesado = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "documento"
        ordering = ["solicitud", "tipo", "-recibido"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.get_estado_display()}"


class EstadoCampo(models.TextChoices):
    OK = "ok", "Confiable"
    REVISAR = "revisar", "Revisar"
    NO_ENCONTRADO = "no_encontrado", "No encontrado"


class MotorCampo(models.TextChoices):
    TESSERACT = "tesseract", "OCR (Tesseract)"
    VISION = "vision", "Modelo de visión"
    FALSO = "falso", "OCR falso (tests)"


class CampoExtraido(models.Model):
    """
    Un dato leído de un documento, con su confianza. El analista lo confirma o lo corrige
    (Parte 2C). INTERNO: la confianza nunca sale por api_clientes.
    """

    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="campos")
    nombre = models.CharField(max_length=40)
    valor_ocr = CampoCifrado(blank=True)         # lo que leyó la máquina (ya normalizado)
    confianza = models.FloatField(default=0)     # 0 a 1
    motor = models.CharField(max_length=20, choices=MotorCampo.choices)
    estado = models.CharField(max_length=20, choices=EstadoCampo.choices)
    observacion = models.CharField(max_length=200, blank=True)   # p. ej. "la CI no coincide con la del frente"

    valor_confirmado = CampoCifrado(blank=True)  # lo que confirmó o corrigió el analista
    confirmado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="+")
    confirmado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "campo extraído"
        verbose_name_plural = "campos extraídos"
        ordering = ["documento", "nombre"]
        constraints = [models.UniqueConstraint(fields=["documento", "nombre"], name="campo_unico_por_documento")]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.confianza:.0%})"
