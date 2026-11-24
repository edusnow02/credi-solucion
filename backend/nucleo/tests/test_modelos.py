"""Tests de parámetros mensuales, roles y del creador del .env."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User

from nucleo import roles
from nucleo.models import ParametroMensual


def _parametro(mes: date, **cambios) -> ParametroMensual:
    datos = dict(mes=mes, tasa_maxima_anual=Decimal("0.27"), tasa_nominal_anual=Decimal("0.25"),
                 pct_max_cuota_ingreso=Decimal("0.30"))
    datos.update(cambios)
    return ParametroMensual.objects.create(**datos)


@pytest.mark.django_db
def test_parametro_se_guarda_en_el_primer_dia_del_mes():
    assert _parametro(date(2026, 11, 24)).mes == date(2026, 11, 1)


@pytest.mark.django_db
def test_vigente_usa_el_mes_o_el_ultimo_anterior():
    octubre = _parametro(date(2026, 10, 1))
    noviembre = _parametro(date(2026, 11, 1))
    assert ParametroMensual.vigente(date(2026, 11, 15)) == noviembre
    assert ParametroMensual.vigente(date(2026, 10, 31)) == octubre
    assert ParametroMensual.vigente(date(2027, 3, 1)) == noviembre   # sin marzo: usa el último
    assert ParametroMensual.vigente(date(2026, 9, 1)) is None


@pytest.mark.django_db
def test_valores_sin_fuente_son_supuestos():
    p = _parametro(date(2026, 11, 1), tasa_maxima_fuente="BCP, circular de noviembre")
    assert "tasa_maxima_anual" not in p.campos_supuestos
    assert set(p.campos_supuestos) == {"tasa_nominal_anual", "pct_max_cuota_ingreso", "cargos"}


@pytest.mark.django_db
def test_existen_los_tres_roles():
    assert set(Group.objects.values_list("name", flat=True)) >= set(roles.TODOS)


@pytest.mark.django_db
def test_tiene_rol():
    usuario = User.objects.create_user("ana", password="clave-larga-de-prueba")
    assert not roles.tiene_rol(usuario, roles.ANALISTA)
    usuario.groups.add(Group.objects.get(name=roles.ANALISTA))
    assert roles.tiene_rol(usuario, roles.ANALISTA)
    assert not roles.tiene_rol(usuario, roles.GERENCIA)
    usuario.is_active = False
    assert not roles.tiene_rol(usuario, roles.ANALISTA)


def test_crear_env_genera_claves_y_no_pisa(tmp_path, monkeypatch):
    import crear_env

    ejemplo = tmp_path / ".env.example"
    ejemplo.write_text("# comentario\nDEBUG=1\nSECRET_KEY=x\nCLAVES_CIFRADO=x\nCLAVE_INDICE=x\n", encoding="utf-8")
    destino = tmp_path / ".env"
    monkeypatch.setattr(crear_env, "EJEMPLO", ejemplo)
    monkeypatch.setattr(crear_env, "DESTINO", destino)

    crear_env.main()
    contenido = destino.read_text(encoding="utf-8")
    assert "DEBUG=1" in contenido and "# comentario" in contenido
    lineas = contenido.splitlines()
    # Comparamos líneas enteras (una clave al azar podría empezar con "x" por casualidad).
    assert "SECRET_KEY=x" not in lineas and "CLAVES_CIFRADO=x" not in lineas and "CLAVE_INDICE=x" not in lineas
    # Segunda vez: no pisa (se perdería la clave de cifrado).
    with pytest.raises(SystemExit):
        crear_env.main()
    assert destino.read_text(encoding="utf-8") == contenido
