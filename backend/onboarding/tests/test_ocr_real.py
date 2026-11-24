"""
Tests con Tesseract REAL sobre imágenes sintéticas dibujadas en el momento.

Si Tesseract no está instalado, se saltean con aviso (en Docker sí está).
"""

import random
import shutil
from datetime import date

import pytest

from datos_sinteticos.documentos import _DIBUJANTES, _degradar, _marca_de_agua
from datos_sinteticos.personas import generar_personas
from onboarding.extraccion import extraer_campos, sin_tildes
from onboarding.preprocesado import leer_con_enderezado

pytestmark = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no está instalado")

CORTE = date(2026, 10, 31)


@pytest.fixture(scope="module")
def motor():
    from onboarding.adaptadores.tesseract import OCRTesseract
    return OCRTesseract()


@pytest.fixture(scope="module")
def asalariada():
    """Una persona sintética del segmento IPS (tiene los cuatro documentos)."""
    rng = random.Random(11)
    return next(p for p in generar_personas(rng, 200) if p.segmento == "ips")


def _leer(motor, persona, tipo, calidad="buena"):
    imagen, verdad = _DIBUJANTES[tipo](persona)
    imagen = _degradar(random.Random(1), _marca_de_agua(imagen), calidad)
    lectura, _ = leer_con_enderezado(motor, imagen)
    return lectura, extraer_campos(lectura, tipo, CORTE), verdad


@pytest.mark.parametrize("tipo, campos", [
    ("ci_frente", ["nombres", "apellidos", "fecha_nacimiento", "sexo"]),
    ("ci_dorso", ["vencimiento"]),
    ("liquidacion", ["nombre", "salario", "fecha_ingreso"]),
    ("extracto_ips", ["salario", "antiguedad_meses"]),
])
def test_imagen_buena_bien_leida_o_marcada_para_revisar(motor, asalariada, tipo, campos):
    """
    Lo importante no es que el OCR nunca se equivoque (se equivoca: por ejemplo "INSFRAAAN"),
    sino que cuando se equivoca la confianza quede POR DEBAJO del umbral, así el analista lo revisa.
    """
    from django.conf import settings

    umbral = settings.ONBOARDING["UMBRAL_CONFIANZA"]
    _, leidos, verdad = _leer(motor, asalariada, tipo)
    aciertos = 0
    for campo in campos:
        bien = sin_tildes(leidos[campo].valor).upper() == sin_tildes(str(verdad[campo])).upper()
        aciertos += bien
        assert bien or leidos[campo].confianza < umbral, f"{campo}: error aceptado sin revisión"
    assert aciertos >= len(campos) - 1   # a lo sumo un campo mal leído por documento


def test_la_ci_se_lee_en_al_menos_tres_de_cuatro_documentos(motor, asalariada):
    # La CI es el dato que más se equivoca (un 8 leído como 3). El cruce entre documentos lo corrige.
    aciertos = sum(_leer(motor, asalariada, t)[1]["ci"].valor == str(asalariada.ci) for t in _DIBUJANTES)
    assert aciertos >= 3


def test_imagen_borrosa_tiene_confianza_baja(motor, asalariada):
    from django.conf import settings

    lectura, _, _ = _leer(motor, asalariada, "ci_dorso", "borrosa")
    assert lectura.confianza_promedio < settings.ONBOARDING["UMBRAL_ILEGIBLE"]


def test_imagen_girada_se_endereza(motor, asalariada):
    imagen, verdad = _DIBUJANTES["ci_dorso"](asalariada)
    girada = _marca_de_agua(imagen).rotate(9, expand=True, fillcolor=(255, 255, 255))
    lectura, angulo = leer_con_enderezado(motor, girada)
    assert angulo != 0
    assert extraer_campos(lectura, "ci_dorso", CORTE)["vencimiento"].valor == verdad["vencimiento"]
