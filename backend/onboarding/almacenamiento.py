"""
Guarda y lee archivos CIFRADOS en disco.

Analogía: una caja fuerte de documentos. Lo que entra se cifra antes de tocar el disco; lo que
sale se descifra en memoria. En el disco nunca queda una cédula legible.
"""

import hashlib
from pathlib import Path

from django.conf import settings

from nucleo.cifrado import cifrar_bytes, descifrar_bytes


def huella(contenido: bytes) -> str:
    """SHA-256 del contenido original (prueba de que no se alteró)."""
    return hashlib.sha256(contenido).hexdigest()


def _ruta_absoluta(relativa: str) -> Path:
    """Convierte la ruta guardada en la base en una ruta real, sin permitir salir de MEDIA_ROOT."""
    raiz = Path(settings.MEDIA_ROOT).resolve()
    ruta = (raiz / relativa).resolve()
    # Defensa: una ruta como "../../etc/passwd" no puede escapar de la carpeta de archivos.
    if raiz not in ruta.parents:
        raise ValueError("Ruta de archivo fuera de la carpeta permitida.")
    return ruta


def guardar_cifrado(contenido: bytes, relativa: str) -> None:
    ruta = _ruta_absoluta(relativa)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(cifrar_bytes(contenido))


def leer_descifrado(relativa: str) -> bytes:
    return descifrar_bytes(_ruta_absoluta(relativa).read_bytes())
