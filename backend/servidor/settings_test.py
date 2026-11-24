"""
Configuración para los tests.

Define claves de PRUEBA antes de cargar la configuración normal, para que los tests corran sin
archivo .env. Estas claves no protegen nada real: solo cifran datos sintéticos que se borran
al terminar cada test.
"""

import os

# setdefault: si ya existen (por ejemplo, en Docker), se respetan.
os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests-no-usar-en-produccion")
# Clave Fernet de prueba (44 caracteres base64). Generada para tests; no se usa en ningún otro lado.
os.environ.setdefault("CLAVES_CIFRADO", "dGVzdHMtdGVzdHMtdGVzdHMtdGVzdHMtdGVzdHMtMDE=")
os.environ.setdefault("CLAVE_INDICE", "indice-solo-para-tests")
# Las tareas de la cola corren en el momento (sin worker) y el OCR por defecto es el falso:
# los tests que necesitan Tesseract real lo piden explícitamente.
os.environ.setdefault("COLA_SINCRONA", "1")
os.environ.setdefault("MOTOR_OCR", "falso")
os.environ.setdefault("MOTOR_VISION", "nulo")

from pathlib import Path  # noqa: E402

from servidor.settings import *  # noqa: E402,F401,F403  (carga todo lo demás igual que en desarrollo)

# Contraseñas: el algoritmo rápido acelera los tests (en producción se usa el normal, lento a propósito).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Archivos subidos de los tests: en una carpeta temporal, nunca en backend/media.
import tempfile  # noqa: E402

MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="credisolucion-tests-"))

