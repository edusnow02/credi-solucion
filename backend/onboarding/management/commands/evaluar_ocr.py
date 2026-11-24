"""
Mide qué tan bien lee el OCR, comparando con la hoja de respuestas (verdad.json) de la Fase 1.

Uso:
    python manage.py evaluar_ocr                 # todas las imágenes de datos_generados/
    python manage.py evaluar_ocr --limite 40     # solo las primeras 40 (más rápido)

Muestra:
1. Aciertos por campo y por calidad de imagen (buena, oscura, girada, borrosa).
2. Detección de ilegibles: cuántas borrosas se marcaron ilegibles y cuántas buenas por error.
3. Para varios umbrales de confianza: qué % de los campos se acepta sin revisión (cobertura)
   y qué % de esos está bien (precisión). Sirve para elegir UMBRAL_CONFIANZA.

No usa la base de datos. Corre el OCR real (Tesseract): tarda unos segundos por imagen.
"""

import json
from collections import Counter
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from onboarding.adaptadores.tesseract import OCRTesseract
from onboarding.extraccion import extraer_campos, sin_tildes
from onboarding.preprocesado import leer_con_enderezado

UMBRALES = [0.6, 0.7, 0.8, 0.85, 0.9, 0.95]


def _igual(leido: str, verdad) -> bool:
    """Comparación sin tildes ni mayúsculas (el OCR a veces pierde una tilde)."""
    return " ".join(sin_tildes(leido).upper().split()) == " ".join(sin_tildes(str(verdad)).upper().split())


class Command(BaseCommand):
    help = "Compara la lectura del OCR con la hoja de respuestas de los datos sintéticos."

    def add_arguments(self, parser):
        parser.add_argument("--carpeta", type=Path, default=settings.CARPETA_SINTETICOS)
        parser.add_argument("--limite", type=int, default=0, help="cantidad máxima de imágenes (0 = todas)")

    def handle(self, *args, **op):
        carpeta: Path = op["carpeta"]
        try:
            verdad = json.loads((carpeta / "verdad.json").read_text(encoding="utf-8"))
            corte = date.fromisoformat(json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))["fecha_corte"])
        except FileNotFoundError as error:
            raise CommandError("Faltan los datos sintéticos: python -m datos_sinteticos.generar") from error

        documentos = [d for d in verdad if d["archivo"]]
        if op["limite"]:
            documentos = documentos[:op["limite"]]
        umbral_ilegible = settings.ONBOARDING["UMBRAL_ILEGIBLE"]
        motor = OCRTesseract()

        aciertos, totales = Counter(), Counter()
        lecturas = []                             # (confianza, acierto) de cada campo
        ilegibles, por_calidad = Counter(), Counter()

        for i, doc in enumerate(documentos, start=1):
            with Image.open(carpeta / doc["archivo"]) as imagen:
                lectura, _ = leer_con_enderezado(motor, imagen)
            campos = extraer_campos(lectura, doc["tipo"], corte)
            calidad = doc["calidad"]
            por_calidad[calidad] += 1
            if not lectura.palabras or lectura.confianza_promedio < umbral_ilegible or not any(c.valor for c in campos.values()):
                ilegibles[calidad] += 1
                continue   # un ilegible no aporta campos (se pide de nuevo al cliente)
            for nombre, leido in campos.items():
                esperado = doc["campos"].get(nombre)
                if esperado is None:
                    continue
                bien = _igual(leido.valor, esperado)
                totales[(nombre, calidad)] += 1
                aciertos[(nombre, calidad)] += bien
                lecturas.append((leido.confianza, bien))
            if i % 20 == 0 or i == len(documentos):
                self.stdout.write(f"  {i}/{len(documentos)} imágenes leídas")

        # 1. Aciertos por campo y calidad.
        self.stdout.write(self.style.MIGRATE_HEADING("Aciertos por campo (sobre imágenes no marcadas ilegibles)"))
        for nombre, calidad in sorted(totales):
            t, a = totales[(nombre, calidad)], aciertos[(nombre, calidad)]
            self.stdout.write(f"  {nombre:<18} {calidad:<8} {a:>4}/{t:<4} {a / t:6.1%}")

        # 2. Ilegibles.
        self.stdout.write(self.style.MIGRATE_HEADING("Marcadas ilegibles por calidad"))
        for calidad, cantidad in sorted(por_calidad.items()):
            self.stdout.write(f"  {calidad:<8} {ilegibles[calidad]:>4}/{cantidad:<4} {ilegibles[calidad] / cantidad:6.1%}")

        # 3. Umbrales.
        self.stdout.write(self.style.MIGRATE_HEADING("Umbral de confianza → cobertura (sin revisión) y precisión"))
        actual = settings.ONBOARDING["UMBRAL_CONFIANZA"]
        for umbral in UMBRALES:
            aceptados = [bien for conf, bien in lecturas if conf >= umbral]
            cobertura = len(aceptados) / len(lecturas) if lecturas else 0
            precision = sum(aceptados) / len(aceptados) if aceptados else 0
            marca = "  ← actual" if abs(umbral - actual) < 1e-9 else ""
            self.stdout.write(f"  {umbral:.2f}   cobertura {cobertura:6.1%}   precisión {precision:6.1%}{marca}")
        self.stdout.write("Precisión = de los campos aceptados sin revisión, cuántos estaban bien.\n"
                          "Recordá: el cruce entre documentos (CI, nombre, salario) atrapa parte de los errores.")
