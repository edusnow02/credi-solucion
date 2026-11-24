"""
Extracción de campos a partir del texto que leyó el OCR. Funciones puras: no tocan la base.

Analogía: un empleado que busca en el papel el rótulo "FECHA DE INGRESO" y copia lo que está
debajo. Si el rótulo está manchado (la marca de agua cruza el texto), busca el dato por su FORMA:
una CI tiene la forma 12.345.678, una fecha dd/mm/aaaa, un monto "G. 1.234.567".

Cada campo sale con su CONFIANZA (0 a 1):
  confianza = la menor confianza del OCR entre las palabras del valor
              × 0,9 si se encontró por la forma y no por el rótulo
              × 0 si el valor no tiene un formato válido (por ejemplo, una fecha 31/02)
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher

from onboarding import config
from onboarding.puertos import PalabraOCR, ResultadoOCR

# Cuántas líneas debajo del rótulo se busca el valor (a veces queda una línea de basura en el medio).
LINEAS_DEBAJO = 2
# Parecido mínimo (0 a 1) entre una línea y el rótulo para darla por encontrada.
PARECIDO_MINIMO = 0.75
# Penalización cuando el valor se encontró por su forma y no debajo de su rótulo.
FACTOR_SIN_ROTULO = 0.9

PATRON_CI = re.compile(r"(?<![\d.])(\d{1,2}[.,]\d{3}[.,]\d{3}|\d{6,9})(?![\d.])")
PATRON_FECHA = re.compile(r"(?<!\d)(\d{2})/(\d{2})/(\d{4})(?!\d)")
PATRON_MONTO = re.compile(r"(-\s*)?G\s*[.,]?\s*(\d{1,3}(?:[.,]\d{3})+)")
PATRON_ENTERO = re.compile(r"(?<!\d)(\d{1,4})(?!\d)")

# Confusiones típicas del OCR en campos que solo llevan dígitos (letra → dígito).
CONFUSIONES_DIGITOS = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"})


@dataclass(frozen=True)
class CampoLeido:
    valor: str           # normalizado ("" si no se encontró)
    confianza: float     # 0 a 1
    por_rotulo: bool     # True si se encontró debajo de su rótulo


@dataclass
class _Linea:
    palabras: list[PalabraOCR]

    @property
    def texto(self) -> str:
        return " ".join(p.texto for p in self.palabras)


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def sin_tildes(texto: str) -> str:
    """'Benítez Ñandú' → 'Benitez Nandu' (para comparar sin que importen las tildes)."""
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _solo_letras(texto: str) -> str:
    """Mayúsculas, sin tildes, solo letras y espacios simples (para comparar rótulos)."""
    limpio = re.sub(r"[^A-Z ]", " ", sin_tildes(texto).upper())
    return re.sub(r"\s+", " ", limpio).strip()


def _es_rotulo(linea: str, rotulo: str) -> bool:
    """¿Esta línea es el rótulo buscado? Admite basura alrededor y algunas letras mal leídas."""
    l, r = _solo_letras(linea), _solo_letras(rotulo)
    if not l:
        return False
    if r in l:
        return True
    # Comparamos el rótulo con cada "ventana" de la línea del mismo largo (por si hay basura a los lados).
    mejor = max((SequenceMatcher(None, r, l[i:i + len(r)]).ratio() for i in range(max(1, len(l) - len(r) + 1))),
                default=0)
    return mejor >= PARECIDO_MINIMO


def _confianza(palabras: list[PalabraOCR]) -> float:
    """Menor confianza entre las palabras que aportan letras o dígitos (ignora símbolos sueltos como '|')."""
    utiles = [p.confianza for p in palabras if re.search(r"[0-9A-Za-zÁÉÍÓÚÑáéíóúñ]", p.texto)]
    return min(utiles) if utiles else 0.0


def _palabras_que_contienen(linea: _Linea, fragmento: str) -> list[PalabraOCR]:
    """Las palabras de la línea que forman parte de un fragmento de texto (para medir su confianza)."""
    partes = set(re.findall(r"[0-9A-Za-zÁÉÍÓÚÑáéíóúñ.,/]+", fragmento))
    elegidas = [p for p in linea.palabras if any(parte in p.texto or p.texto in parte for parte in partes)]
    return elegidas or linea.palabras


# ---------------------------------------------------------------------------
# Lectores por tipo de valor: devuelven (valor normalizado, palabras usadas) o None
# ---------------------------------------------------------------------------

def _leer_ci(linea: _Linea):
    texto = linea.texto.translate(CONFUSIONES_DIGITOS) if re.search(r"\d", linea.texto) else linea.texto
    m = PATRON_CI.search(texto)
    if not m:
        return None
    digitos = re.sub(r"\D", "", m.group(1)).lstrip("0")
    if not (6 <= len(digitos) <= 9):
        return None
    return digitos, _palabras_que_contienen(linea, m.group(1))


def _leer_fecha(linea: _Linea):
    m = PATRON_FECHA.search(linea.texto)
    if not m:
        return None
    dia, mes, anio = (int(x) for x in m.groups())
    try:
        valor = date(anio, mes, dia)
    except ValueError:
        return None   # fecha imposible (31/02): mejor no proponer nada
    if not (1900 <= anio <= 2100):
        return None
    return valor.isoformat(), _palabras_que_contienen(linea, m.group(0))


def _leer_monto(linea: _Linea):
    for m in PATRON_MONTO.finditer(linea.texto):
        if m.group(1):           # "- G. 950.490" es un descuento, no el monto buscado
            continue
        valor = int(re.sub(r"\D", "", m.group(2)))
        if 0 < valor < 10**10:
            return str(valor), _palabras_que_contienen(linea, m.group(2))
    return None


def _leer_entero(linea: _Linea):
    if re.search(r"[A-Za-z]", linea.texto):
        return None              # una línea con letras no es un número suelto
    m = PATRON_ENTERO.search(linea.texto)
    return (str(int(m.group(1))), _palabras_que_contienen(linea, m.group(1))) if m else None


def _leer_nombre(linea: _Linea):
    palabras = [p for p in linea.palabras if re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+", p.texto)]
    if not palabras or sum(len(p.texto) for p in palabras) < 3:
        return None
    return " ".join(p.texto.upper() for p in palabras), palabras


def _leer_texto(linea: _Linea):
    texto = re.sub(r"^[^0-9A-Za-zÁÉÍÓÚÑáéíóúñ]+|[^0-9A-Za-zÁÉÍÓÚÑáéíóúñ.]+$", "", linea.texto)
    if len(texto) < 3:
        return None
    return texto, [p for p in linea.palabras if re.search(r"[0-9A-Za-z]", p.texto)]


def _leer_sexo(linea: _Linea):
    t = _solo_letras(linea.texto)
    for palabra, letra in (("FEMENINO", "F"), ("MASCULINO", "M")):
        if any(SequenceMatcher(None, palabra, w).ratio() >= 0.8 for w in t.split()):
            return letra, linea.palabras
    return None


LECTORES = {
    "ci": _leer_ci, "fecha": _leer_fecha, "monto": _leer_monto, "entero": _leer_entero,
    "nombre": _leer_nombre, "texto": _leer_texto, "sexo": _leer_sexo,
}
# Tipos que se pueden reconocer por su forma aunque el rótulo no aparezca.
TIPOS_CON_FORMA = {"ci", "monto"}


# ---------------------------------------------------------------------------
# Extracción de un documento
# ---------------------------------------------------------------------------

def _buscar(lineas: list[_Linea], rotulo: str, tipo: str) -> CampoLeido:
    lector = LECTORES[tipo]
    # 1) Debajo del rótulo (o en la misma línea, para los montos: "Salario básico G. 1.000.000").
    for i, linea in enumerate(lineas):
        if not _es_rotulo(linea.texto, rotulo):
            continue
        candidatas = ([linea] if tipo == "monto" else []) + lineas[i + 1:i + 1 + LINEAS_DEBAJO + (3 if tipo == "monto" else 0)]
        for candidata in candidatas:
            # Una línea que es otro rótulo no puede ser el valor (salvo el monto en la misma línea).
            leido = lector(candidata)
            if leido:
                valor, palabras = leido
                return CampoLeido(valor, _confianza(palabras), True)
        break
    # 2) Por la forma, en todo el documento.
    if tipo in TIPOS_CON_FORMA:
        for linea in lineas:
            leido = lector(linea)
            if leido:
                valor, palabras = leido
                return CampoLeido(valor, _confianza(palabras) * FACTOR_SIN_ROTULO, False)
    return CampoLeido("", 0.0, False)


def meses_entre(desde: date, hasta: date) -> int:
    """Meses completos entre dos fechas (antigüedad laboral)."""
    meses = (hasta.year - desde.year) * 12 + (hasta.month - desde.month)
    if hasta.day < desde.day:
        meses -= 1
    return max(meses, 0)


def extraer_campos(resultado: ResultadoOCR, tipo_documento: str, fecha_referencia: date | None = None) -> dict[str, CampoLeido]:
    """
    Devuelve {campo: CampoLeido} para los campos de ese tipo de documento (config.CAMPOS_POR_TIPO).
    fecha_referencia: "hoy" para calcular la antigüedad a partir de la fecha de ingreso.
    """
    lineas = [_Linea(grupo) for grupo in resultado.lineas_palabras]
    campos = {
        nombre: _buscar(lineas, definicion["etiqueta"], definicion["tipo"])
        for nombre, definicion in config.CAMPOS_POR_TIPO.get(tipo_documento, {}).items()
    }
    # Dato derivado: antigüedad a partir de la fecha de ingreso de la liquidación.
    if "fecha_ingreso" in campos and campos["fecha_ingreso"].valor:
        ingreso = date.fromisoformat(campos["fecha_ingreso"].valor)
        meses = meses_entre(ingreso, fecha_referencia or date.today())
        campos["antiguedad_meses"] = CampoLeido(str(meses), campos["fecha_ingreso"].confianza,
                                                campos["fecha_ingreso"].por_rotulo)
    return campos
