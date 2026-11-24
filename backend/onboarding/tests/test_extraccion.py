"""
Tests del extractor con texto conocido (sin OCR real): rápidos y siempre iguales.
Los textos imitan lo que Tesseract leyó de verdad en las imágenes sintéticas, con su basura.
"""

from datetime import date

from onboarding.adaptadores.falso import resultado_desde_texto
from onboarding.extraccion import FACTOR_SIN_ROTULO, extraer_campos, meses_entre

FRENTE = """CÉDULA DE IDENTIDAD - MUESTRA SINTÉTICA
-=———, APELLIDOS -
ESPINOLA BRITEZ
NOMBRES
| ANDREA
N.0 DE DOCUMENTO
| 97.481.188
FECHA DE NACIMIENTO
18/07/1971
SEXO
FEMENINO"""

LIQUIDACION = """LIQUIDACIÓN DE HABERES - MUESTRA
Período: 10/2026
EMPLEADOR
Industrias Arasa Morotí S.R.L.
TRABAJADOR
LOURDES ROSA TORRES AYALA
Cl. N.o
96.219.396
FECHA DE INGRESO
10/12/2006
Salario básico G. 10.561.000
Descuento IPS - G. 950.490
NETO ACOBRAR G. 9.610.510"""

EXTRACTO = """EXTRACTO DE APORTES - MUESTRA
ASEGURADO ]
ANDREA ESPÍNOLA BRÍTEZ
Co NO
97.481.188
EMPLEADOR
Logística Paraná Simulada S.A.
MESES DE APORTE CON ESTE EMPLEADOR
125
PERÍODO SALARIO IMPONIBLE
10/2026 G. 7.951.000"""


def _extraer(texto, tipo, confianza=0.95, referencia=date(2026, 10, 31)):
    return extraer_campos(resultado_desde_texto(texto, confianza), tipo, referencia)


def test_frente_de_cedula_aunque_los_rotulos_tengan_basura():
    c = _extraer(FRENTE, "ci_frente")
    assert c["apellidos"].valor == "ESPINOLA BRITEZ"
    assert c["nombres"].valor == "ANDREA"            # el "|" de basura no entra
    assert c["ci"].valor == "97481188"
    assert c["fecha_nacimiento"].valor == "1971-07-18"
    assert c["sexo"].valor == "F"
    assert all(campo.confianza == 0.95 for campo in c.values())


def test_liquidacion_con_salario_en_la_misma_linea_y_sin_tomar_el_descuento():
    c = _extraer(LIQUIDACION, "liquidacion")
    assert c["empleador"].valor == "Industrias Arasa Morotí S.R.L."
    assert c["nombre"].valor == "LOURDES ROSA TORRES AYALA"
    assert c["ci"].valor == "96219396"
    assert c["fecha_ingreso"].valor == "2006-12-10"
    assert c["salario"].valor == "10561000"
    # Antigüedad derivada de la fecha de ingreso: 10/12/2006 → 31/10/2026 = 238 meses.
    assert c["antiguedad_meses"].valor == "238"


def test_salario_en_columna_separada():
    # Tesseract a veces lee la columna de montos aparte, debajo de los conceptos.
    texto = "Salario básico\nDescuento IPS\nNETO A COBRAR\nG. 7.951.000\n- G. 715.590\nG. 7.235.410"
    assert _extraer(texto, "liquidacion")["salario"].valor == "7951000"


def test_extracto_ips_ci_encontrada_por_su_forma_tiene_menos_confianza():
    c = _extraer(EXTRACTO, "extracto_ips")
    assert c["nombre"].valor == "ANDREA ESPÍNOLA BRÍTEZ"
    assert c["antiguedad_meses"].valor == "125"
    assert c["salario"].valor == "7951000"
    # El rótulo "C.I. N.º" salió ilegible ("Co NO"): la CI se encontró por su forma.
    assert c["ci"].valor == "97481188"
    assert not c["ci"].por_rotulo
    assert c["ci"].confianza == 0.95 * FACTOR_SIN_ROTULO


def test_letras_confundidas_con_digitos_en_la_ci():
    c = _extraer("N.º DE DOCUMENTO\n97.48l.l88", "ci_dorso")
    assert c["ci"].valor == "97481188"


def test_fecha_imposible_no_se_propone():
    c = _extraer("FECHA DE VENCIMIENTO\n31/02/2033", "ci_dorso")
    assert c["vencimiento"].valor == "" and c["vencimiento"].confianza == 0


def test_la_confianza_es_la_menor_de_las_palabras_del_valor():
    from onboarding.puertos import PalabraOCR, ResultadoOCR

    resultado = ResultadoOCR(palabras=[
        PalabraOCR("TRABAJADOR", 0.96, 0),
        PalabraOCR("LOURDES", 0.95, 1), PalabraOCR("ROSA", 0.40, 1),
    ])
    assert extraer_campos(resultado, "liquidacion")["nombre"].confianza == 0.40


def test_documento_sin_texto_no_encuentra_nada():
    c = _extraer("", "ci_frente")
    assert all(campo.valor == "" for campo in c.values())


def test_meses_entre():
    assert meses_entre(date(2020, 1, 15), date(2020, 3, 14)) == 1
    assert meses_entre(date(2020, 1, 15), date(2020, 3, 15)) == 2
