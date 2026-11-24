"""
Adaptadores: cada uno conecta un puerto con una herramienta concreta.

obtener_motor_ocr() y obtener_motor_vision() eligen el adaptador según settings.ONBOARDING,
así el resto del código nunca importa Tesseract ni Claude.
"""

from django.conf import settings

from onboarding.puertos import MotorOCR, MotorVision, VerificacionFacial


def obtener_motor_ocr() -> MotorOCR:
    nombre = settings.ONBOARDING["MOTOR_OCR"]
    if nombre == "tesseract":
        from onboarding.adaptadores.tesseract import OCRTesseract
        return OCRTesseract()
    if nombre == "falso":
        from onboarding.adaptadores.falso import OCRFalso
        return OCRFalso()
    raise ValueError(f"MOTOR_OCR desconocido: {nombre!r} (opciones: tesseract, falso)")


def obtener_motor_vision() -> MotorVision:
    nombre = settings.ONBOARDING["MOTOR_VISION"]
    if nombre == "nulo":
        from onboarding.adaptadores.vision_nula import VisionNula
        return VisionNula()
    if nombre == "claude":
        from onboarding.adaptadores.vision_claude import VisionClaude
        return VisionClaude(modelo=settings.ONBOARDING["MODELO_VISION"])
    raise ValueError(f"MOTOR_VISION desconocido: {nombre!r} (opciones: nulo, claude)")


def obtener_verificacion_facial() -> VerificacionFacial:
    # Por ahora solo existe el simulado: un proveedor real necesita contrato y manejo de datos biométricos.
    from onboarding.adaptadores.facial_simulada import VerificacionFacialSimulada
    return VerificacionFacialSimulada()
