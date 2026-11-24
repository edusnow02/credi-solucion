"""
Adaptador de OCR con Tesseract (programa libre, instalado en el sistema o en la imagen de Docker).

pytesseract.image_to_data devuelve, para cada palabra, su texto, su confianza (0 a 100, o -1 si
no es una palabra) y a qué bloque, párrafo y línea pertenece.
"""

import pytesseract
from PIL import Image

from onboarding.puertos import MotorOCR, PalabraOCR, ResultadoOCR


class OCRTesseract(MotorOCR):
    nombre = "tesseract"

    def __init__(self, idioma: str = "spa"):
        self.idioma = idioma

    def leer(self, imagen: Image.Image) -> ResultadoOCR:
        datos = pytesseract.image_to_data(imagen, lang=self.idioma, output_type=pytesseract.Output.DICT)
        palabras = []
        claves_linea: dict[tuple[int, int, int], int] = {}   # (bloque, párrafo, línea) → número correlativo
        for i, texto in enumerate(datos["text"]):
            texto = texto.strip()
            confianza = float(datos["conf"][i])
            if not texto or confianza < 0:   # -1 = no es una palabra (es un bloque o un renglón vacío)
                continue
            clave = (datos["block_num"][i], datos["par_num"][i], datos["line_num"][i])
            numero = claves_linea.setdefault(clave, len(claves_linea))
            palabras.append(PalabraOCR(texto=texto, confianza=confianza / 100, linea=numero))
        return ResultadoOCR(palabras=palabras)
