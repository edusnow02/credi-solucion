"""Tests de la auditoría inmutable y encadenada."""

import copy

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction

from nucleo.auditoria import HASH_INICIAL, registrar, verificar_cadena
from nucleo.models import AuditoriaInmutable, EventoAuditoria

pytestmark = pytest.mark.django_db


def _tres_eventos():
    registrar("sistema", "a", "Solicitud", "1", {"de": "borrador", "a": "en_ocr"})
    registrar("usuario:analista", "b", "Solicitud", "1", {"monto": 5_000_000})
    registrar("sistema", "c", "Pago", "9", {})
    return list(EventoAuditoria.objects.order_by("id"))


def test_cada_evento_cuelga_del_anterior():
    eventos = _tres_eventos()
    assert eventos[0].hash_anterior == HASH_INICIAL
    assert eventos[1].hash_anterior == eventos[0].hash
    assert eventos[2].hash_anterior == eventos[1].hash


def test_la_cadena_intacta_verifica_bien():
    _tres_eventos()
    assert verificar_cadena() == (True, None, 3)


def test_alterar_un_evento_rompe_la_cadena():
    # Simulamos que alguien cambió el actor del segundo evento (en memoria: la base no lo deja).
    eventos = [copy.copy(e) for e in _tres_eventos()]
    eventos[1].actor = "usuario:otro"
    ok, roto, _ = verificar_cadena(eventos)
    assert not ok and roto == eventos[1].id


def test_borrar_un_evento_rompe_la_cadena():
    eventos = _tres_eventos()
    ok, roto, _ = verificar_cadena([eventos[0], eventos[2]])
    assert not ok and roto == eventos[2].id


def test_django_no_deja_modificar_ni_borrar():
    evento = _tres_eventos()[0]
    evento.actor = "otro"
    with pytest.raises(AuditoriaInmutable):
        evento.save()
    with pytest.raises(AuditoriaInmutable):
        evento.delete()
    with pytest.raises(AuditoriaInmutable):
        EventoAuditoria.objects.all().delete()
    with pytest.raises(AuditoriaInmutable):
        EventoAuditoria.objects.update(actor="otro")


@pytest.mark.parametrize("sql", [
    "UPDATE nucleo_eventoauditoria SET actor = 'otro'",
    "DELETE FROM nucleo_eventoauditoria",
])
def test_la_base_rechaza_sql_directo(sql):
    # El trigger de la migración 0003 bloquea incluso a quien se salta Django.
    _tres_eventos()
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql)
    assert EventoAuditoria.objects.count() == 3


def test_no_acepta_datos_personales():
    with pytest.raises(ValueError, match="datos personales"):
        registrar("sistema", "x", "Cliente", "1", {"ci": "91234567"})


def test_comando_verificar_auditoria(capsys):
    _tres_eventos()
    call_command("verificar_auditoria")
    assert "Cadena intacta: 3 eventos" in capsys.readouterr().out


def test_comando_falla_si_la_cadena_esta_rota(monkeypatch):
    monkeypatch.setattr("nucleo.management.commands.verificar_auditoria.verificar_cadena", lambda: (False, 2, 2))
    with pytest.raises(CommandError, match="Cadena rota en el evento #2"):
        call_command("verificar_auditoria")
