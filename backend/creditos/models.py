"""
Solicitudes, créditos, cuotas, pagos y pagarés.

Los montos van en guaraníes ENTEROS (BigIntegerField). Las tasas, en DecimalField (exacto).
Los cálculos NO están acá: están en creditos/reglas.py (una sola calculadora para todo el sistema).
"""

import uuid
from datetime import date

from django.conf import settings
from django.db import models, transaction

from nucleo.auditoria import registrar
from nucleo.models import Canal, Cliente, ParametroMensual, Segmento


class TransicionInvalida(Exception):
    """Se intentó pasar una solicitud a un estado que no corresponde (por ejemplo, de rechazada a aprobada)."""


# ---------------------------------------------------------------------------
# Solicitud
# ---------------------------------------------------------------------------

class EstadoSolicitud(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    FALTAN_DOCUMENTOS = "faltan_documentos", "Faltan documentos"
    EN_OCR = "en_ocr", "Leyendo documentos"
    EN_REVISION = "en_revision", "En revisión"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"
    DESISTIDA = "desistida", "Desistida"


# Mapa de caminos permitidos: desde cada estado, a cuáles se puede pasar.
# Como un semáforo con reglas: de "rechazada" no se vuelve a "aprobada".
TRANSICIONES = {
    EstadoSolicitud.BORRADOR: {EstadoSolicitud.FALTAN_DOCUMENTOS, EstadoSolicitud.EN_OCR, EstadoSolicitud.DESISTIDA},
    EstadoSolicitud.FALTAN_DOCUMENTOS: {EstadoSolicitud.EN_OCR, EstadoSolicitud.DESISTIDA},
    EstadoSolicitud.EN_OCR: {EstadoSolicitud.EN_REVISION, EstadoSolicitud.FALTAN_DOCUMENTOS},
    EstadoSolicitud.EN_REVISION: {EstadoSolicitud.APROBADA, EstadoSolicitud.RECHAZADA,
                                  EstadoSolicitud.FALTAN_DOCUMENTOS, EstadoSolicitud.DESISTIDA},
    EstadoSolicitud.APROBADA: set(),     # estados finales: no salen a ningún lado
    EstadoSolicitud.RECHAZADA: set(),
    EstadoSolicitud.DESISTIDA: set(),
}


class Solicitud(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="solicitudes")
    monto_pedido = models.BigIntegerField()
    plazo_meses = models.PositiveSmallIntegerField()
    canal = models.CharField(max_length=20, choices=Canal.choices)
    estado = models.CharField(max_length=20, choices=EstadoSolicitud.choices, default=EstadoSolicitud.BORRADOR)

    # Ingreso que PROPONE el OCR (salario leído de la liquidación o del extracto de IPS). Provisorio.
    ingreso_propuesto = models.BigIntegerField(null=True, blank=True)
    ingreso_confirmado = models.BigIntegerField(null=True, blank=True)   # lo confirma el analista
    # Calculada con reglas.cuota_maxima sobre el ingreso confirmado o, mientras no lo haya, el propuesto.
    cuota_maxima = models.BigIntegerField(null=True, blank=True)
    analista = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="solicitudes_asignadas")
    notas_analista = models.TextField(blank=True)    # INTERNO: nunca sale por api_clientes
    motivo_rechazo = models.TextField(blank=True)    # se le muestra al cliente en lenguaje simple

    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "solicitud"
        verbose_name_plural = "solicitudes"
        ordering = ["-creada"]

    def __str__(self) -> str:
        return f"Solicitud {str(self.id)[:8]} — {self.get_estado_display()}"

    def cambiar_estado(self, nuevo: str, actor: str, motivo: str = "") -> None:
        """
        Única forma de cambiar el estado: valida el camino y deja el evento en la auditoría,
        todo en la misma transacción (o se guardan las dos cosas, o ninguna).
        """
        actual = EstadoSolicitud(self.estado)
        nuevo = EstadoSolicitud(nuevo)
        if nuevo not in TRANSICIONES[actual]:
            raise TransicionInvalida(f"No se puede pasar de '{actual.label}' a '{nuevo.label}'.")
        with transaction.atomic():
            self.estado = nuevo
            if nuevo == EstadoSolicitud.RECHAZADA:
                self.motivo_rechazo = motivo
            self.save(update_fields=["estado", "motivo_rechazo", "actualizada"])
            registrar(actor, "estado_cambiado", "Solicitud", self.id, {"de": actual.value, "a": nuevo.value})


# ---------------------------------------------------------------------------
# Crédito y cuotas
# ---------------------------------------------------------------------------

class EstadoCredito(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    EN_MORA = "en_mora", "En mora"
    CANCELADO = "cancelado", "Cancelado"
    CASTIGADO = "castigado", "Castigado"
    REFINANCIADO = "refinanciado", "Refinanciado"


class Credito(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_externo = models.CharField(max_length=20, blank=True, db_index=True)   # K00001 en datos sintéticos
    solicitud = models.OneToOneField(Solicitud, on_delete=models.PROTECT, related_name="credito")

    monto = models.BigIntegerField()
    plazo_meses = models.PositiveSmallIntegerField()
    tasa_nominal_anual = models.DecimalField(max_digits=7, decimal_places=4)
    cargos = models.JSONField(default=list, blank=True)        # copia de los cargos aplicados
    costo_total = models.BigIntegerField(null=True, blank=True)
    tasa_efectiva_anual = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    cumple_tasa_maxima_nominal = models.BooleanField(null=True, blank=True)
    cumple_tasa_maxima_efectiva = models.BooleanField(null=True, blank=True)
    cumple_regla_apple = models.BooleanField(null=True, blank=True)   # INTERNO
    # Parámetros vigentes al aprobar. Vacío en los créditos históricos cargados de datos sintéticos.
    parametro = models.ForeignKey(ParametroMensual, null=True, blank=True, on_delete=models.PROTECT)

    fecha_desembolso = models.DateField()
    cosecha = models.CharField(max_length=7, db_index=True, editable=False)   # "AAAA-MM", sale de la fecha
    # Copias para filtrar el dashboard sin unir tablas (sucursal y segmento no son datos personales).
    sucursal = models.CharField(max_length=60, db_index=True)
    segmento = models.CharField(max_length=20, choices=Segmento.choices, db_index=True)
    canal = models.CharField(max_length=20, choices=Canal.choices, db_index=True)
    estado = models.CharField(max_length=20, choices=EstadoCredito.choices, default=EstadoCredito.VIGENTE)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "crédito"
        ordering = ["-fecha_desembolso"]

    def __str__(self) -> str:
        return f"Crédito {self.codigo_externo or str(self.id)[:8]} — G. {self.monto:,}".replace(",", ".")

    def save(self, *args, **kwargs):
        self.cosecha = self.fecha_desembolso.strftime("%Y-%m")
        super().save(*args, **kwargs)


class EstadoCuota(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    PAGADA = "pagada", "Pagada"
    ATRASADA = "atrasada", "Atrasada"


class Cuota(models.Model):
    credito = models.ForeignKey(Credito, on_delete=models.CASCADE, related_name="cuotas")
    numero = models.PositiveSmallIntegerField()
    vencimiento = models.DateField(db_index=True)
    capital = models.BigIntegerField()
    interes = models.BigIntegerField()
    cargos = models.BigIntegerField(default=0)
    total = models.BigIntegerField()
    estado = models.CharField(max_length=20, choices=EstadoCuota.choices, default=EstadoCuota.PENDIENTE)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "cuota"
        ordering = ["credito", "numero"]
        constraints = [models.UniqueConstraint(fields=["credito", "numero"], name="cuota_unica_por_credito")]

    def __str__(self) -> str:
        return f"Cuota {self.numero} de {self.credito}"

    def dias_atraso(self, hoy: date) -> int:
        """Días de atraso: al pagar si está pagada; a 'hoy' si sigue impaga y vencida; 0 si no venció."""
        if self.fecha_pago:
            return max((self.fecha_pago - self.vencimiento).days, 0)
        return max((hoy - self.vencimiento).days, 0)


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------

class MedioPago(models.TextChoices):
    SUCURSAL = "sucursal", "Sucursal"
    BOCA_COBRANZA = "boca_cobranza", "Boca de cobranza"
    TRANSFERENCIA = "transferencia", "Transferencia"
    APP = "app", "App (pasarela)"


class Pago(models.Model):
    """
    Pago confirmado. Se guardan TODOS, también los puntuales (idea del Cadastro Positivo).
    Los pagos nuevos se registran con su evento de auditoría (Parte 2C y Fase 6);
    los históricos de datos sintéticos se cargan en bloque con un solo evento de resumen.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_externo = models.CharField(max_length=24, blank=True, db_index=True)
    credito = models.ForeignKey(Credito, on_delete=models.PROTECT, related_name="pagos")
    cuota = models.ForeignKey(Cuota, null=True, blank=True, on_delete=models.PROTECT, related_name="pagos")
    fecha = models.DateField(db_index=True)
    monto = models.BigIntegerField()
    medio = models.CharField(max_length=20, choices=MedioPago.choices)
    comprobante_sha256 = models.CharField(max_length=64, blank=True)
    registrado_por = models.CharField(max_length=120)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pago"
        ordering = ["-fecha"]

    def __str__(self) -> str:
        return f"Pago {self.fecha} — G. {self.monto:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Pagaré
# ---------------------------------------------------------------------------

class EstadoPagare(models.TextChoices):
    EMITIDO = "emitido", "Emitido"
    FIRMADO = "firmado", "Firmado"
    DEVUELTO = "devuelto", "Devuelto al cliente"
    ANULADO = "anulado", "Anulado"


class Pagare(models.Model):
    """
    Pagaré del crédito. En el prototipo es un PDF marcado MUESTRA (Parte 2C lo genera).
    El hash prueba que el archivo no se alteró; cada cambio de estado queda en la auditoría.
    Al cancelar el crédito, el pagaré se DEVUELVE o ANULA (lección de la "mafia de los pagarés").
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credito = models.ForeignKey(Credito, on_delete=models.PROTECT, related_name="pagares")
    archivo = models.CharField(max_length=300, blank=True)     # ruta del archivo CIFRADO dentro de MEDIA_ROOT
    sha256 = models.CharField(max_length=64, blank=True)       # huella del PDF original (sin cifrar)
    estado = models.CharField(max_length=20, choices=EstadoPagare.choices, default=EstadoPagare.EMITIDO)
    emitido = models.DateTimeField(auto_now_add=True)
    firmado_en = models.DateTimeField(null=True, blank=True)
    devuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "pagaré"

    def __str__(self) -> str:
        return f"Pagaré de {self.credito} — {self.get_estado_display()}"
