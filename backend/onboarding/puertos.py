"""
Puertos del onboarding: las "formas de enchufe" que el resto del sistema conoce.

El sistema habla con estos puertos, nunca con Tesseract ni con Claude directamente. Para cambiar
de motor se cambia el adaptador (el "cable") en la configuración, sin tocar la lógica.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PalabraOCR:
    texto: str
    confianza: float     # 0 a 1
    linea: int           # número de línea (las palabras de la misma línea comparten número)


@dataclass
class ResultadoOCR:
    palabras: list[PalabraOCR] = field(default_factory=list)

    @property
    def lineas_palabras(self) -> list[list[PalabraOCR]]:
        """Las palabras agrupadas por línea, en orden de lectura."""
        por_linea: dict[int, list[PalabraOCR]] = {}
        for p in self.palabras:
            por_linea.setdefault(p.linea, []).append(p)
        return [grupo for _, grupo in sorted(por_linea.items())]

    @property
    def lineas(self) -> list[tuple[str, float]]:
        """Lista de (texto de la línea, confianza mínima de sus palabras), en orden de lectura."""
        return [(" ".join(p.texto for p in g), min(p.confianza for p in g)) for g in self.lineas_palabras]

    @property
    def texto(self) -> str:
        return "\n".join(t for t, _ in self.lineas)

    @property
    def confianza_promedio(self) -> float:
        if not self.palabras:
            return 0.0
        return sum(p.confianza for p in self.palabras) / len(self.palabras)


class MotorOCR(ABC):
    """Lee el texto de una imagen y dice qué tan seguro está de cada palabra."""

    nombre = "ocr"
    # False en motores que no miran la imagen (el falso de los tests): no tiene sentido girarla.
    admite_enderezado = True

    @abstractmethod
    def leer(self, imagen: Image.Image) -> ResultadoOCR: ...


# ---------------------------------------------------------------------------
# Visión (respaldo para los campos dudosos)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CampoVision:
    valor: str           # "" si no lo encontró
    confianza: float     # 0 a 1, AUTODECLARADA por el modelo (no está calibrada: el analista revisa igual)


class ErrorVision(Exception):
    """El motor de visión no pudo responder (red, límite de uso, rechazo). El campo queda para revisar."""


class MotorVision(ABC):
    """Mira la imagen completa y propone el valor de los campos pedidos."""

    # False = no hay motor de visión: los campos dudosos quedan "para revisar" sin consultar a nadie.
    disponible = False

    @abstractmethod
    def extraer(self, imagen: bytes, tipo_mime: str, tipo_documento: str, campos: list[str]) -> dict[str, CampoVision]: ...


# ---------------------------------------------------------------------------
# Verificación facial
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoFacial:
    simulado: bool                  # True = no se comparó nada de verdad (la interfaz lo tiene que decir)
    coincide: bool | None           # None = no se sabe
    detalle: str


class VerificacionFacial(ABC):
    @abstractmethod
    def comparar(self, selfie: bytes, foto_ci: bytes | None) -> ResultadoFacial: ...
