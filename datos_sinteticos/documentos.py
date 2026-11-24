"""
Dibuja imágenes FALSAS de documentos y su "hoja de respuestas".

- Cédula (frente y dorso): diseño PROPIO con los mismos campos que la cédula paraguaya, pero sin
  imitar el documento oficial (imitarlo es riesgoso legalmente). Todo lleva la marca de agua
  "MUESTRA - SIN VALOR".
- Liquidación de sueldo y extracto de aportes IPS: formatos inventados (los reales están por confirmar).
- Algunas imágenes salen a propósito borrosas, giradas u oscuras, y algunas faltan, para probar en la
  Fase 2 que el sistema detecta documentos ilegibles o faltantes.

Hoja de respuestas (verdad.json): para cada imagen, los valores correctos de cada campo. En la Fase 2
compara lo que leyó el OCR con la verdad y mide cuánto acierta.
"""

import random
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from datos_sinteticos import supuestos
from datos_sinteticos.azar import elegir_con_peso
from datos_sinteticos.personas import Persona, formatear_ci

# Fuentes de letra a probar, en orden: Fedora, Debian/Ubuntu (Docker). Si ninguna existe, se usa
# la fuente que trae Pillow. Liberation Sans es libre (licencia SIL OFL).
_FUENTES = [
    "/usr/share/fonts/liberation-sans-fonts/LiberationSans-{estilo}.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-{estilo}.ttf",
]

BLANCO = (255, 255, 255)
NEGRO = (20, 20, 20)
GRIS = (110, 110, 110)
CELESTE = (225, 236, 245)
MARCA = (215, 215, 215)


@dataclass
class DocumentoSintetico:
    cliente_id: str
    tipo: str                      # ci_frente | ci_dorso | liquidacion | extracto_ips
    calidad: str                   # buena | borrosa | girada | oscura | faltante
    archivo: str | None            # ruta relativa a la carpeta de salida; None si falta
    campos: dict = field(default_factory=dict)   # la verdad: valores correctos


def _fuente(tamanio: int, negrita: bool = False) -> ImageFont.FreeTypeFont:
    """Carga la fuente en el tamaño pedido (en píxeles)."""
    estilo = "Bold" if negrita else "Regular"
    for patron in _FUENTES:
        ruta = Path(patron.format(estilo=estilo))
        if ruta.exists():
            return ImageFont.truetype(str(ruta), tamanio)
    # Respaldo: la fuente incluida en Pillow (≥ 10.1 acepta tamaño).
    return ImageFont.load_default(size=tamanio)


def _guaranies(monto: int) -> str:
    """3044000 → 'G. 3.044.000'."""
    return "G. " + f"{monto:,}".replace(",", ".")


def _fecha(f: date) -> str:
    """Fecha en formato dd/mm/aaaa."""
    return f.strftime("%d/%m/%Y")


def _marca_de_agua(imagen: Image.Image) -> Image.Image:
    """Escribe 'MUESTRA - SIN VALOR' en diagonal, en gris claro, sobre toda la imagen."""
    ancho, alto = imagen.size
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    fuente = _fuente(max(ancho // 14, 20), negrita=True)
    # Repetimos el texto en varias filas para que cubra el documento entero.
    for fila in range(-1, 6):
        dibujo.text((ancho * 0.05, alto * fila / 5), supuestos.MARCA_DE_AGUA, font=fuente, fill=MARCA + (150,))
    capa = capa.rotate(18, resample=Image.BICUBIC)
    base = imagen.convert("RGBA")
    base.alpha_composite(capa)
    return base.convert("RGB")


def _degradar(rng: random.Random, imagen: Image.Image, calidad: str) -> Image.Image:
    """Aplica el defecto pedido para simular una foto mala."""
    if calidad == "borrosa":
        return imagen.filter(ImageFilter.GaussianBlur(radius=rng.uniform(3.0, 4.5)))
    if calidad == "girada":
        angulo = rng.choice([-1, 1]) * rng.uniform(5, 12)
        return imagen.rotate(angulo, expand=True, fillcolor=BLANCO, resample=Image.BICUBIC)
    if calidad == "oscura":
        return ImageEnhance.Brightness(imagen).enhance(rng.uniform(0.25, 0.4))
    return imagen


# ---------------------------------------------------------------------------
# Dibujo de cada tipo de documento
# ---------------------------------------------------------------------------

def _renglon(dibujo, x, y, etiqueta, valor, fuente_etiqueta, fuente_valor) -> int:
    """Escribe 'ETIQUETA' chica arriba y el valor grande abajo; devuelve la y del siguiente renglón."""
    dibujo.text((x, y), etiqueta, font=fuente_etiqueta, fill=GRIS)
    dibujo.text((x, y + 22), valor, font=fuente_valor, fill=NEGRO)
    return y + 66


def _cedula_frente(p: Persona) -> tuple[Image.Image, dict]:
    imagen = Image.new("RGB", (1012, 638), CELESTE)       # proporción de tarjeta (85,6 × 54 mm)
    d = ImageDraw.Draw(imagen)
    f_titulo, f_et, f_val = _fuente(30, True), _fuente(18), _fuente(30, True)
    d.text((40, 28), "CÉDULA DE IDENTIDAD - MUESTRA SINTÉTICA", font=f_titulo, fill=NEGRO)
    # Recuadro de la "foto" (vacío: no generamos caras).
    d.rectangle((40, 110, 290, 430), outline=GRIS, width=3, fill=BLANCO)
    d.text((115, 255), "FOTO", font=f_val, fill=GRIS)
    y = 100
    y = _renglon(d, 330, y, "APELLIDOS", p.apellidos.upper(), f_et, f_val)
    y = _renglon(d, 330, y, "NOMBRES", p.nombres.upper(), f_et, f_val)
    y = _renglon(d, 330, y, "N.º DE DOCUMENTO", formatear_ci(p.ci), f_et, f_val)
    y = _renglon(d, 330, y, "FECHA DE NACIMIENTO", _fecha(p.fecha_nacimiento), f_et, f_val)
    _renglon(d, 330, y, "SEXO", "FEMENINO" if p.sexo == "F" else "MASCULINO", f_et, f_val)
    campos = {
        "apellidos": p.apellidos.upper(),
        "nombres": p.nombres.upper(),
        "nombre": p.nombre_completo.upper(),
        "ci": str(p.ci),
        "fecha_nacimiento": p.fecha_nacimiento.isoformat(),
        "sexo": p.sexo,
    }
    return imagen, campos


def _cedula_dorso(p: Persona) -> tuple[Image.Image, dict]:
    imagen = Image.new("RGB", (1012, 638), CELESTE)
    d = ImageDraw.Draw(imagen)
    f_titulo, f_et, f_val = _fuente(30, True), _fuente(18), _fuente(30, True)
    d.text((40, 28), "DORSO - MUESTRA SINTÉTICA", font=f_titulo, fill=NEGRO)
    # Fechas de emisión y vencimiento derivadas de forma fija (no hacen falta al azar).
    emision = date(supuestos.FECHA_CORTE.year - 3, p.fecha_nacimiento.month, min(p.fecha_nacimiento.day, 28))
    vencimiento = date(emision.year + 10, emision.month, emision.day)
    y = 100
    y = _renglon(d, 40, y, "N.º DE DOCUMENTO", formatear_ci(p.ci), f_et, f_val)
    y = _renglon(d, 40, y, "DOMICILIO", p.sucursal.upper(), f_et, f_val)
    y = _renglon(d, 40, y, "FECHA DE EMISIÓN", _fecha(emision), f_et, f_val)
    _renglon(d, 40, y, "FECHA DE VENCIMIENTO", _fecha(vencimiento), f_et, f_val)
    campos = {"ci": str(p.ci), "vencimiento": vencimiento.isoformat()}
    return imagen, campos


def _liquidacion(p: Persona) -> tuple[Image.Image, dict]:
    imagen = Image.new("RGB", (1240, 1000), BLANCO)
    d = ImageDraw.Draw(imagen)
    f_titulo, f_et, f_val = _fuente(36, True), _fuente(20), _fuente(28)
    periodo = supuestos.FECHA_CORTE.strftime("%m/%Y")
    d.text((60, 40), "LIQUIDACIÓN DE HABERES - MUESTRA", font=f_titulo, fill=NEGRO)
    d.text((60, 95), f"Período: {periodo}", font=f_val, fill=NEGRO)
    d.line((60, 145, 1180, 145), fill=GRIS, width=2)
    y = 170
    y = _renglon(d, 60, y, "EMPLEADOR", p.empleador, f_et, f_val)
    y = _renglon(d, 60, y, "TRABAJADOR", p.nombre_completo.upper(), f_et, f_val)
    y = _renglon(d, 60, y, "C.I. N.º", formatear_ci(p.ci), f_et, f_val)
    y = _renglon(d, 60, y, "CARGO", p.cargo, f_et, f_val)
    fecha_ingreso = _fecha(p.fecha_ingreso_laboral) if p.fecha_ingreso_laboral else "-"
    y = _renglon(d, 60, y, "FECHA DE INGRESO", fecha_ingreso, f_et, f_val)
    d.line((60, y + 5, 1180, y + 5), fill=GRIS, width=2)
    # Jubilados no aportan al IPS en esta muestra; asalariados y funcionarios sí (simplificación).
    descuento = 0 if p.segmento == "jubilado" else int(
        (Decimal(p.ingreso_mensual) * supuestos.APORTE_IPS_OBRERO).quantize(Decimal("1"))
    )
    neto = p.ingreso_mensual - descuento
    y += 30
    for concepto, monto in [("Salario básico", p.ingreso_mensual), ("Descuento IPS", -descuento), ("NETO A COBRAR", neto)]:
        d.text((60, y), concepto, font=f_val, fill=NEGRO)
        texto = _guaranies(abs(monto))
        if monto < 0:
            texto = "- " + texto
        d.text((800, y), texto, font=f_val, fill=NEGRO)
        y += 50
    campos = {
        "nombre": p.nombre_completo.upper(),
        "ci": str(p.ci),
        "empleador": p.empleador,
        "salario": p.ingreso_mensual,
        "fecha_ingreso": p.fecha_ingreso_laboral.isoformat() if p.fecha_ingreso_laboral else None,
        "antiguedad_meses": p.antiguedad_meses_en(supuestos.FECHA_CORTE),
    }
    return imagen, campos


def _extracto_ips(p: Persona) -> tuple[Image.Image, dict]:
    imagen = Image.new("RGB", (1240, 1240), BLANCO)
    d = ImageDraw.Draw(imagen)
    f_titulo, f_et, f_val, f_tabla = _fuente(36, True), _fuente(20), _fuente(28), _fuente(24)
    d.text((60, 40), "EXTRACTO DE APORTES - MUESTRA", font=f_titulo, fill=NEGRO)
    y = 110
    y = _renglon(d, 60, y, "ASEGURADO", p.nombre_completo.upper(), f_et, f_val)
    y = _renglon(d, 60, y, "C.I. N.º", formatear_ci(p.ci), f_et, f_val)
    y = _renglon(d, 60, y, "EMPLEADOR", p.empleador, f_et, f_val)
    antiguedad = p.antiguedad_meses_en(supuestos.FECHA_CORTE) or 0
    y = _renglon(d, 60, y, "MESES DE APORTE CON ESTE EMPLEADOR", str(antiguedad), f_et, f_val)
    # Tabla de los últimos meses de aporte (hasta 6, o menos si la antigüedad es menor).
    d.text((60, y + 10), "PERÍODO", font=f_et, fill=GRIS)
    d.text((400, y + 10), "SALARIO IMPONIBLE", font=f_et, fill=GRIS)
    d.text((800, y + 10), "APORTE", font=f_et, fill=GRIS)
    y += 45
    aporte = int((Decimal(p.ingreso_mensual) * supuestos.APORTE_IPS_OBRERO).quantize(Decimal("1")))
    for atras in range(min(6, antiguedad)):
        # Mes "atras" meses antes del corte.
        total = supuestos.FECHA_CORTE.year * 12 + supuestos.FECHA_CORTE.month - 1 - atras
        periodo = f"{total % 12 + 1:02d}/{total // 12}"
        d.text((60, y), periodo, font=f_tabla, fill=NEGRO)
        d.text((400, y), _guaranies(p.ingreso_mensual), font=f_tabla, fill=NEGRO)
        d.text((800, y), _guaranies(aporte), font=f_tabla, fill=NEGRO)
        y += 40
    campos = {
        "nombre": p.nombre_completo.upper(),
        "ci": str(p.ci),
        "empleador": p.empleador,
        "salario": p.ingreso_mensual,
        "antiguedad_meses": antiguedad,
    }
    return imagen, campos


_DIBUJANTES = {
    "ci_frente": _cedula_frente,
    "ci_dorso": _cedula_dorso,
    "liquidacion": _liquidacion,
    "extracto_ips": _extracto_ips,
}


def generar_documentos(rng: random.Random, personas: list[Persona], carpeta: Path) -> list[DocumentoSintetico]:
    """
    Dibuja los documentos que corresponden al segmento de cada persona y los guarda en
    carpeta/documentos/<id_cliente>/<tipo>.jpg. Devuelve la lista con la verdad de cada uno.
    """
    resultado = []
    for p in personas:
        for tipo in supuestos.SEGMENTOS[p.segmento]["documentos"]:
            calidad = elegir_con_peso(rng, supuestos.CALIDAD_DOCUMENTOS)
            imagen, campos = _DIBUJANTES[tipo](p)
            if calidad == "faltante":
                # El cliente "no mandó" este documento: no hay archivo, pero sí registro de la verdad.
                resultado.append(DocumentoSintetico(p.id, tipo, calidad, None, campos))
                continue
            imagen = _degradar(rng, _marca_de_agua(imagen), calidad)
            relativa = Path("documentos") / p.id / f"{tipo}.jpg"
            destino = carpeta / relativa
            destino.parent.mkdir(parents=True, exist_ok=True)
            # JPEG calidad 85: parecido a una foto de celular y liviano.
            imagen.save(destino, "JPEG", quality=85)
            resultado.append(DocumentoSintetico(p.id, tipo, calidad, str(relativa), campos))
    return resultado
