"""Tests de los modelos de créditos: estados de la solicitud y su auditoría."""

from datetime import date

import pytest

from creditos.models import Credito, Cuota, EstadoSolicitud, Solicitud, TransicionInvalida
from nucleo.auditoria import verificar_cadena
from nucleo.models import Cliente, EventoAuditoria

pytestmark = pytest.mark.django_db


@pytest.fixture
def solicitud():
    cliente = Cliente(ci="91234567", nombres="Ana", apellidos="Benítez", segmento="ips",
                      sucursal="Luque", canal_origen="web")
    cliente.save()
    return Solicitud.objects.create(cliente=cliente, monto_pedido=5_000_000, plazo_meses=12, canal="web")


def test_camino_normal_deja_un_evento_por_paso(solicitud):
    for estado in ["en_ocr", "en_revision", "aprobada"]:
        solicitud.cambiar_estado(estado, "usuario:analista")
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.APROBADA
    eventos = EventoAuditoria.objects.filter(entidad="Solicitud", entidad_id=str(solicitud.id))
    assert [e.datos["a"] for e in eventos] == ["en_ocr", "en_revision", "aprobada"]
    assert verificar_cadena()[0]


def test_no_se_puede_saltar_la_revision(solicitud):
    with pytest.raises(TransicionInvalida):
        solicitud.cambiar_estado("aprobada", "usuario:analista")


def test_rechazada_es_final_y_guarda_el_motivo(solicitud):
    solicitud.cambiar_estado("en_ocr", "sistema")
    solicitud.cambiar_estado("en_revision", "sistema")
    solicitud.cambiar_estado("rechazada", "usuario:analista", motivo="La cuota supera la capacidad de pago.")
    solicitud.refresh_from_db()
    assert solicitud.motivo_rechazo.startswith("La cuota")
    with pytest.raises(TransicionInvalida):
        solicitud.cambiar_estado("aprobada", "usuario:analista")


def test_transicion_invalida_no_deja_evento(solicitud):
    antes = EventoAuditoria.objects.count()
    with pytest.raises(TransicionInvalida):
        solicitud.cambiar_estado("aprobada", "usuario:analista")
    assert EventoAuditoria.objects.count() == antes


def test_cosecha_sale_de_la_fecha_de_desembolso(solicitud):
    credito = Credito.objects.create(solicitud=solicitud, monto=5_000_000, plazo_meses=12, tasa_nominal_anual="0.25",
                                     fecha_desembolso=date(2025, 12, 3), sucursal="Luque", segmento="ips", canal="web")
    assert credito.cosecha == "2025-12"


def test_dias_de_atraso_de_una_cuota(solicitud):
    credito = Credito.objects.create(solicitud=solicitud, monto=1, plazo_meses=1, tasa_nominal_anual="0",
                                     fecha_desembolso=date(2026, 1, 1), sucursal="Luque", segmento="ips", canal="web")
    cuota = Cuota(credito=credito, numero=1, vencimiento=date(2026, 2, 1), capital=1, interes=0, total=1)
    assert cuota.dias_atraso(date(2026, 1, 20)) == 0          # todavía no venció
    assert cuota.dias_atraso(date(2026, 2, 11)) == 10         # impaga, 10 días después
    cuota.fecha_pago = date(2026, 2, 5)
    assert cuota.dias_atraso(date(2026, 3, 1)) == 4           # pagada con 4 días de atraso
