"""
OCR falso para tests: devuelve un texto preparado de antemano, sin mirar la imagen.

Sirve para probar la extracción y el flujo sin depender de Tesseract (rápido y siempre igual).
Uso en un test:
    OCRFalso.respuestas = ["APELLIDOS\\nBENITEZ ORTIZ\\n..."]   # una por cada lectura, en orden
"""

from PIL import Image

from onboarding.puertos import MotorOCR, PalabraOCR, ResultadoOCR


def resultado_desde_texto(texto: str, confianza: float = 0.95) -> ResultadoOCR:
    """Convierte un texto de varias líneas en un ResultadoOCR con la misma confianza en cada palabra."""
    palabras = []
    for numero, linea in enumerate(texto.splitlines()):
        for palabra in linea.split():
            palabras.append(PalabraOCR(texto=palabra, confianza=confianza, linea=numero))
    return ResultadoOCR(palabras=palabras)


class OCRFalso(MotorOCR):
    nombre = "falso"
    admite_enderezado = False
    # Cola de respuestas compartida (los tests la llenan). Cada respuesta: texto o ResultadoOCR.
    respuestas: list = []

    def leer(self, imagen: Image.Image) -> ResultadoOCR:
        if not OCRFalso.respuestas:
            return ResultadoOCR()      # sin respuesta preparada = imagen sin texto
        respuesta = OCRFalso.respuestas.pop(0)
        return respuesta if isinstance(respuesta, ResultadoOCR) else resultado_desde_texto(respuesta)
