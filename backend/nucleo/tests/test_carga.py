"""Test de punta a punta: generar datos sintéticos y cargarlos en la base."""

from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from creditos.models import Credito, Cuota, Pago, Solicitud
from datos_sinteticos.generar import generar
from nucleo.auditoria import verificar_cadena
from nucleo.models import Cliente, EventoAuditoria, ParametroMensual

pytestmark = pytest.mark.django_db

HOY = date(2026, 11, 30)


@pytest.fixture
def carpeta(tmp_path):
    """Genera 150 clientes sintéticos (sin imágenes) en una carpeta temporal."""
    destino = tmp_path / "datos"
    generar(150, 5, 0, False, destino)
    return destino


def test_carga_completa(carpeta):
    call_command("cargar_sinteticos", carpeta=carpeta, hoy=HOY, stdout=open("/dev/null", "w"))

    assert Cliente.objects.count() == 150
    assert Credito.objects.count() == Solicitud.objects.count() == 150
    assert Cuota.objects.count() > 150 * 12 - 1
    assert Pago.objects.count() > 0
    # Cada pago apunta a una cuota pagada del mismo crédito.
    pago = Pago.objects.select_related("cuota").first()
    assert pago.cuota.credito_id == pago.credito_id and pago.cuota.estado == "pagada"
    # Ningún pago en el futuro: las fechas se movieron para que el corte sea HOY.
    assert not Pago.objects.filter(fecha__gt=HOY).exists()
    assert Credito.objects.filter(fecha_desembolso__gt=HOY).count() == 0
    # La cosecha coincide con la fecha ya desplazada.
    credito = Credito.objects.first()
    assert credito.cosecha == credito.fecha_desembolso.strftime("%Y-%m")
    # Parámetros SUPUESTOS del mes y la auditoría intacta con el evento de carga.
    assert ParametroMensual.vigente(HOY).campos_supuestos
    assert EventoAuditoria.objects.filter(accion="carga_sintetica").exists()
    assert verificar_cadena()[0]


def test_los_datos_cargados_quedan_cifrados(carpeta):
    call_command("cargar_sinteticos", carpeta=carpeta, hoy=HOY, stdout=open("/dev/null", "w"))
    with connection.cursor() as cursor:
        cursor.execute("SELECT ci, nombres FROM nucleo_cliente LIMIT 5")
        filas = cursor.fetchall()
    assert all(ci.startswith("gAAAAA") and nombres.startswith("gAAAAA") for ci, nombres in filas)
    # Y se pueden buscar por CI con el índice.
    cualquiera = Cliente.objects.first()
    assert Cliente.buscar_por_ci(cualquiera.ci) == cualquiera


def test_no_carga_dos_veces(carpeta):
    call_command("cargar_sinteticos", carpeta=carpeta, hoy=HOY, stdout=open("/dev/null", "w"))
    with pytest.raises(CommandError, match="Ya hay datos sintéticos"):
        call_command("cargar_sinteticos", carpeta=carpeta, hoy=HOY)


def test_avisa_si_no_hay_datos_generados(tmp_path):
    with pytest.raises(CommandError, match="Generá los datos"):
        call_command("cargar_sinteticos", carpeta=tmp_path / "vacia")
