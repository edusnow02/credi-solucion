"""
Modelos compartidos por todos los módulos.

Recordatorio para quien sabe SQL: cada clase es un CREATE TABLE y cada atributo una columna.
Django genera el SQL en las "migraciones" (python manage.py makemigrations / migrate).
"""

import uuid
from datetime import date

from django.conf import settings
from django.db import models

from nucleo.cifrado import CampoCifrado, indice_ci, normalizar_ci


# ---------------------------------------------------------------------------
# Opciones fijas (las "listas desplegables" de la base)
# ---------------------------------------------------------------------------

class Segmento(models.TextChoices):
    IPS = "ips", "Asalariado con IPS"
    FUNCIONARIO = "funcionario", "Funcionario público"
    JUBILADO = "jubilado", "Jubilado"
    INFORMAL = "informal", "Trabajador informal"
    INDEPENDIENTE = "independiente", "Independiente"
    IVA = "iva", "Contribuyente de IVA"
    PYME = "pyme", "Pyme"
    AGRO = "agro", "Agro"


class Canal(models.TextChoices):
    APP = "app", "App"
    TELEGRAM = "telegram", "Telegram"
    WHATSAPP = "whatsapp", "WhatsApp"
    WEB = "web", "Formulario web"
    TELEFONO = "telefono", "Teléfono"
    SUCURSAL = "sucursal", "Sucursal"


class Sexo(models.TextChoices):
    FEMENINO = "F", "Femenino"
    MASCULINO = "M", "Masculino"
    SIN_DATO = "", "Sin dato"


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------

class Cliente(models.Model):
    """
    Persona que pide o tiene créditos. Los datos personales van CIFRADOS (CampoCifrado).
    Para buscar por CI se usa ci_indice (huella), nunca la CI en claro.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Código del generador de datos sintéticos (C00001…). Vacío para clientes cargados de verdad.
    codigo_externo = models.CharField(max_length=20, blank=True, db_index=True)

    ci = CampoCifrado("CI")
    ci_indice = models.CharField("huella de la CI", max_length=64, unique=True, editable=False)
    nombres = CampoCifrado()
    apellidos = CampoCifrado()
    telefono = CampoCifrado(blank=True)
    correo = CampoCifrado(blank=True)
    # Fecha guardada como texto "AAAA-MM-DD" cifrado (un campo de fecha no se puede cifrar).
    fecha_nacimiento_cifrada = CampoCifrado("fecha de nacimiento", blank=True)
    # Sexo: SOLO para medir sesgo en la Fase 5; nunca es variable del score.
    sexo = models.CharField(max_length=1, choices=Sexo.choices, blank=True)

    segmento = models.CharField(max_length=20, choices=Segmento.choices)
    sucursal = models.CharField(max_length=60)
    canal_origen = models.CharField(max_length=20, choices=Canal.choices)

    # Datos laborales (personales → cifrados). Los confirma el analista en cada solicitud.
    empleador = CampoCifrado(blank=True)
    cargo = CampoCifrado(blank=True)
    fecha_ingreso_laboral_cifrada = CampoCifrado("fecha de ingreso laboral", blank=True)
    ingreso_mensual_cifrado = CampoCifrado("ingreso mensual", blank=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cliente"

    def __str__(self) -> str:
        # Mostramos solo el código y el final de la CI, nunca el nombre completo (por si aparece en registros).
        return f"Cliente {self.codigo_externo or str(self.id)[:8]} (CI …{str(self.ci)[-3:]})"

    # --- Propiedades: convierten los textos cifrados en fechas y números al leer ----------
    @property
    def fecha_nacimiento(self) -> date | None:
        return date.fromisoformat(self.fecha_nacimiento_cifrada) if self.fecha_nacimiento_cifrada else None

    @fecha_nacimiento.setter
    def fecha_nacimiento(self, valor: date | None) -> None:
        self.fecha_nacimiento_cifrada = valor.isoformat() if valor else ""

    @property
    def fecha_ingreso_laboral(self) -> date | None:
        return date.fromisoformat(self.fecha_ingreso_laboral_cifrada) if self.fecha_ingreso_laboral_cifrada else None

    @fecha_ingreso_laboral.setter
    def fecha_ingreso_laboral(self, valor: date | None) -> None:
        self.fecha_ingreso_laboral_cifrada = valor.isoformat() if valor else ""

    @property
    def ingreso_mensual(self) -> int | None:
        return int(self.ingreso_mensual_cifrado) if self.ingreso_mensual_cifrado else None

    @ingreso_mensual.setter
    def ingreso_mensual(self, valor: int | None) -> None:
        self.ingreso_mensual_cifrado = str(int(valor)) if valor is not None else ""

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"

    # --- Guardado y búsqueda ------------------------------------------------------------
    def save(self, *args, **kwargs):
        # La CI se guarda normalizada (solo dígitos) y su huella se recalcula siempre.
        self.ci = normalizar_ci(self.ci)
        self.ci_indice = indice_ci(self.ci)
        super().save(*args, **kwargs)

    @classmethod
    def buscar_por_ci(cls, ci) -> "Cliente | None":
        """Busca por CI en cualquier formato ('1.234.567' o '1234567') usando la huella."""
        return cls.objects.filter(ci_indice=indice_ci(ci)).first()


# ---------------------------------------------------------------------------
# Parámetros mensuales
# ---------------------------------------------------------------------------

class ParametroMensual(models.Model):
    """
    Valores que cambian con el tiempo o que decide la empresa. Uno por mes.

    Cada valor tiene su "fuente". Si la fuente está vacía, el valor es SUPUESTO y la interfaz lo
    tiene que mostrar como tal (regla del proyecto: no inventar parámetros sin avisar).
    """

    mes = models.DateField("mes (primer día)", unique=True)

    tasa_maxima_anual = models.DecimalField(
        "tasa máxima anual (BCP)", max_digits=7, decimal_places=4,
        help_text="Por ejemplo 0,2707 = 27,07 %. Se compara con la tasa nominal y con la efectiva.",
    )
    tasa_maxima_fuente = models.CharField(max_length=300, blank=True)

    tasa_nominal_anual = models.DecimalField(
        "tasa nominal anual ofrecida", max_digits=7, decimal_places=4,
        help_text="Tasa que la empresa cobra a los créditos nuevos de este mes.",
    )
    tasa_nominal_fuente = models.CharField(max_length=300, blank=True)

    pct_max_cuota_ingreso = models.DecimalField(
        "% máximo de cuota sobre ingreso", max_digits=5, decimal_places=4,
        help_text="Por ejemplo 0,30 = la cuota no puede superar el 30 % del ingreso.",
    )
    pct_cuota_fuente = models.CharField(max_length=300, blank=True)

    # Lista de cargos: [{"concepto": "...", "tipo": "...", "valor": "..."}]. Tipos en creditos/reglas.py.
    cargos = models.JSONField(default=list, blank=True)
    cargos_fuente = models.CharField(max_length=300, blank=True)

    actualizado = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "parámetro mensual"
        verbose_name_plural = "parámetros mensuales"
        ordering = ["-mes"]

    def __str__(self) -> str:
        return f"Parámetros {self.mes:%m/%Y}"

    def save(self, *args, **kwargs):
        # Siempre el primer día del mes, así "noviembre" es una sola fila.
        self.mes = self.mes.replace(day=1)
        super().save(*args, **kwargs)

    @property
    def campos_supuestos(self) -> list[str]:
        """Nombres de los valores que no tienen fuente (= SUPUESTO)."""
        fuentes = {
            "tasa_maxima_anual": self.tasa_maxima_fuente,
            "tasa_nominal_anual": self.tasa_nominal_fuente,
            "pct_max_cuota_ingreso": self.pct_cuota_fuente,
            "cargos": self.cargos_fuente,
        }
        return [campo for campo, fuente in fuentes.items() if not fuente.strip()]

    @classmethod
    def vigente(cls, fecha: date) -> "ParametroMensual | None":
        """Los parámetros del mes de 'fecha' o, si no hay, los del último mes cargado antes."""
        return cls.objects.filter(mes__lte=fecha).order_by("-mes").first()


# ---------------------------------------------------------------------------
# Auditoría inmutable
# ---------------------------------------------------------------------------

class AuditoriaInmutable(Exception):
    """Error que se lanza si alguien intenta modificar o borrar un evento de auditoría."""


class _EventosQuerySet(models.QuerySet):
    """Bloquea las operaciones masivas que modificarían eventos (update y delete de muchos a la vez)."""

    def update(self, **kwargs):
        raise AuditoriaInmutable("Los eventos de auditoría no se modifican.")

    def delete(self):
        raise AuditoriaInmutable("Los eventos de auditoría no se borran.")


class EventoAuditoria(models.Model):
    """
    Libro de actas foliado: cada renglón guarda la huella (hash) del anterior.

    Tres candados:
    1. Este modelo no deja modificar ni borrar desde Django.
    2. Un trigger en la base (migración 0003) rechaza UPDATE y DELETE incluso desde SQL directo.
    3. Si alguien igual lo lograra (por ejemplo, con permisos de administrador de la base),
       el comando verificar_auditoria detecta la cadena rota.

    Los eventos se crean SOLO con nucleo.auditoria.registrar(), que calcula los hashes.
    'datos' nunca lleva datos personales en claro (registrar() lo controla).
    """

    id = models.BigAutoField(primary_key=True)
    fecha = models.DateTimeField()
    actor = models.CharField(max_length=120)        # "usuario:analista", "sistema", "cliente:<id>"
    accion = models.CharField(max_length=60, db_index=True)
    entidad = models.CharField(max_length=60)       # "Solicitud", "Credito", "Pago"…
    entidad_id = models.CharField(max_length=64, db_index=True)
    datos = models.JSONField(default=dict, blank=True)
    # unique en hash_anterior: dos eventos no pueden "colgar" del mismo anterior (evita bifurcaciones).
    hash_anterior = models.CharField(max_length=64, unique=True)
    hash = models.CharField(max_length=64, unique=True)

    objects = _EventosQuerySet.as_manager()

    class Meta:
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"#{self.id} {self.accion} {self.entidad} {self.entidad_id}"

    def save(self, *args, **kwargs):
        # Si ya tiene id, ya está guardado: guardarlo de nuevo sería modificarlo.
        if self.pk is not None and not kwargs.get("force_insert"):
            raise AuditoriaInmutable("Los eventos de auditoría no se modifican.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditoriaInmutable("Los eventos de auditoría no se borran.")


# ---------------------------------------------------------------------------
# Cuenta de cliente (acceso a la app). Mínima en la Fase 2; se completa en la etapa 2.
# ---------------------------------------------------------------------------

class CuentaCliente(models.Model):
    """
    Acceso de un cliente a la app. Separada del usuario de Django a propósito:
    un cliente nunca puede tener rol de personal ni entrar al panel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cliente = models.OneToOneField(Cliente, on_delete=models.PROTECT, related_name="cuenta")
    activa = models.BooleanField(default=True)
    pin_hash = models.CharField(max_length=200, blank=True)   # hash del PIN, nunca el PIN
    ultimo_ingreso = models.DateTimeField(null=True, blank=True)
    eliminacion_pedida = models.DateTimeField(null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cuenta de cliente"
        verbose_name_plural = "cuentas de clientes"

    def __str__(self) -> str:
        return f"Cuenta de {self.cliente}"

