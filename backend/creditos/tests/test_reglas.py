"""
Tests de las reglas de crédito.

Cada test es una pregunta con respuesta conocida: si la calculadora responde distinto, algo se rompió.
Se corren con:  pytest
"""

from datetime import date
from decimal import Decimal

import pytest

from creditos.reglas import (
    cronograma,
    cuota_francesa,
    sumar_meses,
    tasa_mensual_desde_nominal_anual,
)


def test_cuota_francesa_caso_calculado_a_mano():
    # G. 1.000.000 al 2 % mensual en 12 cuotas.
    # A mano: 1.000.000 × 0,02 × 1,02^12 / (1,02^12 − 1) = 94.559,60 → G. 94.560
    assert cuota_francesa(1_000_000, Decimal("0.02"), 12) == 94_560


def test_cuota_sin_interes_es_monto_dividido_plazo():
    assert cuota_francesa(1_200_000, Decimal("0"), 12) == 100_000


def test_tasa_mensual_es_nominal_anual_dividida_doce():
    assert tasa_mensual_desde_nominal_anual(Decimal("0.24")) == Decimal("0.02")


@pytest.mark.parametrize("monto, plazo", [(0, 12), (-5, 12), (1_000_000, 0)])
def test_datos_imposibles_dan_error(monto, plazo):
    # Un monto o plazo imposible tiene que fallar con un error, no devolver un número.
    with pytest.raises(ValueError):
        cuota_francesa(monto, Decimal("0.02"), plazo)


@pytest.mark.parametrize("monto", [3_000_000, 5_000_000, 10_000_000, 7_777_777])
@pytest.mark.parametrize("plazo", [6, 12, 18, 24, 36])
def test_capital_del_cronograma_suma_exactamente_el_monto(monto, plazo):
    # Con los montos más pedidos y plazos comunes, la suma del capital no puede perder ni un guaraní.
    cuotas = cronograma(monto, Decimal("0.025"), plazo, date(2026, 1, 15))
    assert sum(c.capital for c in cuotas) == monto
    assert cuotas[-1].saldo_despues == 0
    assert len(cuotas) == plazo


def test_cuotas_intermedias_son_iguales_y_la_ultima_casi():
    cuotas = cronograma(5_000_000, Decimal("0.025"), 12, date(2026, 1, 15))
    fija = cuota_francesa(5_000_000, Decimal("0.025"), 12)
    # Todas las cuotas menos la última son exactamente la cuota fija.
    assert all(c.total == fija for c in cuotas[:-1])
    # La última difiere a lo sumo en unos pocos guaraníes por los redondeos.
    assert abs(cuotas[-1].total - fija) <= plazo_tolerancia(12)


def plazo_tolerancia(plazo: int) -> int:
    # Cada mes el redondeo puede mover hasta medio guaraní: tolerancia = un guaraní por cuota.
    return plazo


def test_vencimientos_mensuales_y_fin_de_mes():
    cuotas = cronograma(3_000_000, Decimal("0.02"), 3, date(2026, 1, 31))
    # 31 de enero + 1 mes → 28 de febrero (2026 no es bisiesto).
    assert [c.vencimiento for c in cuotas] == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_sumar_meses_cruza_el_anio():
    assert sumar_meses(date(2025, 11, 10), 3) == date(2026, 2, 10)
