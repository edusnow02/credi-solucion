"""
Motor de visión "nulo" (el que se usa por defecto): no consulta a nadie.

Los campos dudosos quedan marcados "revisar" para el analista. No sale ningún dato del sistema.
"""

from onboarding.puertos import CampoVision, MotorVision


class VisionNula(MotorVision):
    disponible = False

    def extraer(self, imagen: bytes, tipo_mime: str, tipo_documento: str, campos: list[str]) -> dict[str, CampoVision]:
        return {}
