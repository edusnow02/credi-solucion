"""
Tests de la Fase 2 de las reglas: cargos, costo total, tasa efectiva, cuota máxima y topes.
Cada caso tiene la cuenta hecha a mano en el comentario.
"""

from datetime import date
from decimal import Decimal

import pytest

from creditos.reglas import (
    Cargo,
    aplicar_cargos,
    cargos_iniciales,
    cronograma,
    cuota_maxima,
    simular,
    tasa_efectiva_anual,
)

DESEMBOLSO = date(2026, 1, 15)


def test_cuota_maxima_redondea_hacia_abajo():
    # 3.044.000 × 0,30 = 913.200 exacto; 3.044.001 × 0,30 = 913.200,3 → 913.200 (nunca hacia arriba).
    assert cuota_maxima(3_044_000, Decimal("0.30")) == 913_200
    assert cuota_maxima(3_044_001, Decimal("0.30")) == 913_200


@pytest.mark.parametrize("pct", [Decimal("-0.1"), Decimal("1.5")])
def test_cuota_maxima_rechaza_porcentajes_imposibles(pct):
    with pytest.raises(ValueError):
        cuota_maxima(1_000_000, pct)


def test_tasa_efectiva_sin_cargos_es_la_nominal_capitalizada():
    # TNA 24 % → 2 % mensual → TEA = 1,02^12 − 1 = 26,824 %.
    cuotas = cronograma(5_000_000, Decimal("0.02"), 12, DESEMBOLSO)
    tea = tasa_efectiva_anual(5_000_000, [c.total for c in cuotas])
    assert abs(tea - Decimal("0.268242")) < Decimal("0.0001")


def test_tasa_efectiva_cero_si_no_hay_costo():
    assert tasa_efectiva_anual(1_200_000, [100_000] * 12) == 0


def test_cargos_mensuales():
    cuotas = cronograma(1_000_000, Decimal("0.02"), 2, DESEMBOLSO)
    # Cuota 1: interés 20.000. Saldo antes: 1.000.000.
    #   fijo 5.000 + 10 % del interés (2.000) + 0,1 % del saldo (1.000) = 8.000
    cargos = [Cargo("fijo", "mensual_fijo", Decimal("5000")), Cargo("imp", "pct_interes", Decimal("0.10")),
              Cargo("seguro", "pct_saldo", Decimal("0.001"))]
    con_cargos = aplicar_cargos(cuotas, cargos)
    assert con_cargos[0].cargos == 8_000
    assert con_cargos[0].total == cuotas[0].total + 8_000


def test_cargos_iniciales():
    # 2 % de 5.000.000 = 100.000 + fijo 50.000 = 150.000
    cargos = [Cargo("adm", "inicial_pct", Decimal("0.02")), Cargo("fijo", "inicial_fijo", Decimal("50000"))]
    assert cargos_iniciales(5_000_000, cargos) == 150_000


def test_cargo_desconocido_da_error():
    with pytest.raises(ValueError):
        Cargo.desde_dict({"concepto": "x", "tipo": "inventado", "valor": "1"})


def test_simular_junta_todo():
    s = simular(
        5_000_000, 12, Decimal("0.24"), DESEMBOLSO,
        cargos=[Cargo.desde_dict({"concepto": "Gastos", "tipo": "inicial_pct", "valor": "0.02"})],
        tasa_maxima_anual=Decimal("0.2707"), ingreso_mensual=3_044_000, pct_max_cuota_ingreso=Decimal("0.30"),
    )
    assert s.monto_liquido == 4_900_000                       # recibe 5.000.000 − 2 %
    assert s.costo_total == s.total_cuotas + 100_000
    assert s.costo_financiero == s.costo_total - 5_000_000
    # Nominal 24 % ≤ 27,07 %: cumple. Con los gastos iniciales la efectiva supera 26,82 %.
    assert s.cumple_tasa_maxima_nominal is True
    assert s.tasa_efectiva_anual > Decimal("0.268242")
    # Cuota ≈ 472.800 ≤ cuota máxima 913.200.
    assert s.cuota_maxima == 913_200 and s.entra_en_capacidad_de_pago is True
    assert s.cumple_regla_apple is True


def test_simular_detecta_que_no_entra_en_la_capacidad_de_pago():
    s = simular(10_000_000, 12, Decimal("0.24"), DESEMBOLSO,
                ingreso_mensual=2_000_000, pct_max_cuota_ingreso=Decimal("0.30"))
    assert s.entra_en_capacidad_de_pago is False


def test_regla_de_apple():
    # TNA 40 % → TEA ≈ 48 % > 36 %: no cumple.
    assert simular(3_000_000, 12, Decimal("0.40"), DESEMBOLSO).cumple_regla_apple is False
    # 2 meses ≈ 59 días ≤ 60: no cumple aunque la tasa sea baja.
    assert simular(3_000_000, 2, Decimal("0.10"), DESEMBOLSO).cumple_regla_apple is False


def test_tasa_maxima_compara_nominal_y_efectiva_por_separado():
    # Nominal 26 % ≤ 27,07 %, pero efectiva ≈ 29,3 % > 27,07 %: las dos respuestas difieren.
    s = simular(5_000_000, 12, Decimal("0.26"), DESEMBOLSO, tasa_maxima_anual=Decimal("0.2707"))
    assert s.cumple_tasa_maxima_nominal is True
    assert s.cumple_tasa_maxima_efectiva is False


def test_sin_tope_ni_ingreso_las_comparaciones_quedan_vacias():
    s = simular(3_000_000, 12, Decimal("0.25"), DESEMBOLSO)
    assert s.cumple_tasa_maxima_nominal is None and s.cuota_maxima is None
