"""Tests del cifrado de datos personales y del índice ciego."""

import pytest
from django.db import connection

from nucleo.cifrado import cifrar_bytes, cifrar_texto, descifrar_bytes, descifrar_texto, indice_ci, normalizar_ci
from nucleo.models import Cliente


def _cliente(**cambios) -> Cliente:
    datos = dict(ci="91.234.567", nombres="Ana María", apellidos="Benítez Ortiz", telefono="0900 123 456",
                 segmento="ips", sucursal="Luque", canal_origen="web", empleador="Empresa Ficticia S.A.")
    datos.update(cambios)
    c = Cliente(**datos)
    c.ingreso_mensual = 5_000_000
    c.save()
    return c


def test_cifrar_y_descifrar_texto_y_bytes():
    assert descifrar_texto(cifrar_texto("Ñandutí 123")) == "Ñandutí 123"
    assert descifrar_bytes(cifrar_bytes(b"\x00imagen")) == b"\x00imagen"


def test_el_mismo_texto_se_cifra_distinto_cada_vez():
    # Por eso los campos cifrados no se pueden buscar directamente: hace falta el índice ciego.
    assert cifrar_texto("Ana") != cifrar_texto("Ana")


def test_un_texto_alterado_no_se_descifra():
    cifrado = cifrar_texto("dato")
    alterado = cifrado[:-2] + ("A" if cifrado[-2] != "A" else "B") + cifrado[-1]
    with pytest.raises(ValueError):
        descifrar_texto(alterado)


@pytest.mark.parametrize("entrada", ["91.234.567", "91234567", " 91234567 ", 91234567, "091234567"])
def test_normalizar_ci_acepta_formatos_comunes(entrada):
    assert normalizar_ci(entrada) == "91234567"


def test_indice_ci_es_igual_para_el_mismo_numero_en_distinto_formato():
    assert indice_ci("91.234.567") == indice_ci(91234567)
    assert indice_ci("91.234.567") != indice_ci("91.234.568")


@pytest.mark.django_db
def test_en_la_base_los_datos_personales_no_estan_en_claro():
    _cliente()
    with connection.cursor() as cursor:
        cursor.execute("SELECT ci, nombres, apellidos, telefono, empleador, ingreso_mensual_cifrado FROM nucleo_cliente")
        fila = cursor.fetchone()
    texto = " ".join(fila)
    for dato in ["91234567", "Ana", "Benítez", "0900", "Ficticia", "5000000"]:
        assert dato not in texto
    # Los cifrados de Fernet empiezan con "gAAAAA".
    assert all(valor.startswith("gAAAAA") for valor in fila)


@pytest.mark.django_db
def test_al_leer_desde_django_los_datos_vuelven_en_claro():
    creado = _cliente()
    leido = Cliente.objects.get(pk=creado.pk)
    assert leido.ci == "91234567"
    assert leido.nombre_completo == "Ana María Benítez Ortiz"
    assert leido.ingreso_mensual == 5_000_000


@pytest.mark.django_db
def test_buscar_por_ci_en_cualquier_formato():
    creado = _cliente()
    assert Cliente.buscar_por_ci("91234567") == creado
    assert Cliente.buscar_por_ci("91.234.567") == creado
    assert Cliente.buscar_por_ci("99.999.999") is None


@pytest.mark.django_db
def test_no_puede_haber_dos_clientes_con_la_misma_ci():
    from django.db import IntegrityError, transaction

    _cliente()
    with pytest.raises(IntegrityError), transaction.atomic():
        _cliente(ci="91234567", nombres="Otra")
