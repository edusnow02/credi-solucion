"""
Preparación de la imagen antes del OCR.

Analogía: antes de leer un papel arrugado, lo alisás y lo ponés a la luz.
- Escala de grises + autocontraste: arregla las fotos oscuras (estira los grises del negro al blanco).
- Enderezado: si la primera lectura sale con poca confianza, prueba girar la imagen unos grados y se
  queda con la lectura que más texto confiable obtuvo.

Probado con los documentos sintéticos: binarizar (pasar a blanco y negro puro) para borrar la marca
de agua EMPEORA la lectura, porque también come partes de las letras. Por eso no se hace.
"""

from PIL import Image, ImageOps

from onboarding import config
from onboarding.puertos import MotorOCR, ResultadoOCR


def preparar(imagen: Image.Image) -> Image.Image:
    """Escala de grises + autocontraste. exif_transpose respeta la orientación que guardó el celular."""
    imagen = ImageOps.exif_transpose(imagen)
    return ImageOps.autocontrast(imagen.convert("L"), cutoff=1)


def _puntaje(resultado: ResultadoOCR) -> float:
    """Cuánto texto confiable hay: suma de la confianza de las palabras razonablemente seguras (≥ 0,6)."""
    return sum(p.confianza for p in resultado.palabras if p.confianza >= 0.6)


def leer_con_enderezado(motor: MotorOCR, imagen: Image.Image) -> tuple[ResultadoOCR, int]:
    """
    Lee la imagen; si la confianza es baja, prueba los ángulos de config.ANGULOS_ENDEREZADO.
    Devuelve (mejor resultado, ángulo usado).
    """
    preparada = preparar(imagen)
    mejor = motor.leer(preparada)
    angulo_mejor = 0
    if not motor.admite_enderezado or (
            mejor.confianza_promedio >= config.CONFIANZA_PARA_REINTENTAR and len(mejor.palabras) >= 8):
        return mejor, 0   # la primera lectura ya es buena: no gastamos tiempo en girar
    for angulo in config.ANGULOS_ENDEREZADO:
        # expand=True agranda el lienzo para no cortar las esquinas; el relleno es blanco (255).
        girada = preparada.rotate(angulo, expand=True, fillcolor=255, resample=Image.BICUBIC)
        intento = motor.leer(girada)
        if _puntaje(intento) > _puntaje(mejor):
            mejor, angulo_mejor = intento, angulo
    return mejor, angulo_mejor
