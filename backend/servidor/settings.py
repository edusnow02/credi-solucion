"""
Configuración del backend.

Analogía: es el tablero de control del edificio. Todo lo que cambia entre tu computadora, Docker y
Render (claves, base de datos, modo de depuración) se lee de variables de entorno o del archivo .env,
nunca se escribe acá. Así el código se puede subir a git sin secretos.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# BASE_DIR = carpeta backend/; RAIZ = raíz del monorepo (donde está el .env).
BASE_DIR = Path(__file__).resolve().parent.parent
RAIZ = BASE_DIR.parent

# Lee el archivo .env de la raíz si existe. No pisa variables ya definidas (las de Docker mandan).
load_dotenv(RAIZ / ".env")


def _bool(nombre: str, defecto: bool = False) -> bool:
    """Lee una variable de entorno como sí/no ("1", "true", "si" = sí)."""
    return os.environ.get(nombre, str(defecto)).strip().lower() in {"1", "true", "si", "sí", "yes"}


def _lista(nombre: str) -> list[str]:
    """Lee una variable separada por comas como lista, sin espacios ni vacíos."""
    return [x.strip() for x in os.environ.get(nombre, "").split(",") if x.strip()]


def _obligatoria(nombre: str) -> str:
    """Lee una variable que tiene que existir; si falta, el servidor no arranca (mejor que arrancar inseguro)."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise ImproperlyConfigured(
            f"Falta la variable {nombre}. Creá el archivo .env con: python crear_env.py (en la carpeta backend)"
        )
    return valor


# ---------------------------------------------------------------------------
# Seguridad básica
# ---------------------------------------------------------------------------
DEBUG = _bool("DEBUG")
SECRET_KEY = _obligatoria("SECRET_KEY")
ALLOWED_HOSTS = _lista("ALLOWED_HOSTS") or (["localhost", "127.0.0.1"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = _lista("CSRF_TRUSTED_ORIGINS")

# Claves de los datos personales (ver nucleo/cifrado.py).
# CLAVES_CIFRADO admite varias separadas por coma: la primera cifra, todas descifran
# (permite cambiar la clave sin perder lo ya guardado).
CLAVES_CIFRADO = _lista("CLAVES_CIFRADO")
if not CLAVES_CIFRADO:
    raise ImproperlyConfigured("Falta CLAVES_CIFRADO. Creá el archivo .env con: python crear_env.py (en la carpeta backend)")
CLAVE_INDICE = _obligatoria("CLAVE_INDICE")

if not DEBUG:
    # En producción: solo HTTPS y cookies que no viajan por conexiones sin cifrar.
    SECURE_SSL_REDIRECT = _bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_q",          # cola de tareas (procesa el OCR en segundo plano)
    # Apps del proyecto
    "nucleo",
    "creditos",
    "onboarding",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "servidor.urls"
WSGI_APPLICATION = "servidor.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Base de datos: PostgreSQL si hay DATABASE_URL; si no, SQLite local (solo desarrollo).
# ---------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
    )
}
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    # SQLite admite un solo escritor a la vez: que los demás esperen hasta 20 s en vez de fallar
    # con "database is locked" (pasa con la web y el worker escribiendo a la vez).
    DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 20
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Contraseñas del personal: mínimo 10 caracteres y las validaciones estándar de Django.
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Idioma y hora
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Asuncion"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos (CSS y JS) y archivos subidos
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Los documentos subidos se guardan CIFRADOS en esta carpeta y nunca se sirven directo:
# solo a través de una vista que verifica permisos (Parte 2C).
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

# Carpeta de los datos sintéticos de la Fase 1 (la lee cargar_sinteticos).
CARPETA_SINTETICOS = Path(os.environ.get("CARPETA_SINTETICOS", RAIZ / "datos_generados"))

# ---------------------------------------------------------------------------
# Cola de tareas (django-q2). Usa la misma base de datos como "fila": no hace falta Redis.
# Se pone a trabajar con:  python manage.py qcluster   (en Docker: el servicio "worker")
# ---------------------------------------------------------------------------
Q_CLUSTER = {
    "name": "credisolucion",
    "orm": "default",                    # la fila de tareas vive en la base de datos
    "workers": int(os.environ.get("COLA_TRABAJADORES", "2")),
    "timeout": 120,                      # una tarea que tarda más de 2 minutos se corta
    "retry": 180,                        # y se reintenta a los 3 minutos (debe ser mayor que timeout)
    "max_attempts": 3,
    "catch_up": False,
    # En los tests (y si COLA_SINCRONA=1) las tareas corren en el momento, sin worker.
    "sync": _bool("COLA_SINCRONA"),
}

# ---------------------------------------------------------------------------
# Onboarding (Módulo A): qué motor de OCR y de visión usar, y el umbral de confianza.
# ---------------------------------------------------------------------------
ONBOARDING = {
    # Adaptadores (puertos y adaptadores: se cambia el "cable" sin tocar el resto del sistema).
    "MOTOR_OCR": os.environ.get("MOTOR_OCR", "tesseract"),        # tesseract | falso
    "MOTOR_VISION": os.environ.get("MOTOR_VISION", "nulo"),       # nulo (por defecto) | claude
    # Confianza mínima (0 a 1) para aceptar un campo sin consultar al motor de visión.
    # No es un dato regulatorio: es técnico y se ajusta midiendo con "python manage.py evaluar_ocr".
    # 0,90 medido el 24/11/2026 con 105 imágenes sintéticas: 99,4 % de precisión, 84 % sin revisión.
    "UMBRAL_CONFIANZA": float(os.environ.get("UMBRAL_CONFIANZA", "0.90")),
    # Si la confianza promedio de TODO el documento es menor a esto, el documento es "ilegible".
    "UMBRAL_ILEGIBLE": float(os.environ.get("UMBRAL_ILEGIBLE", "0.45")),
    # Modelo de Claude para el respaldo de visión (solo si MOTOR_VISION=claude).
    "MODELO_VISION": os.environ.get("MODELO_VISION", "claude-opus-5-5"),
}

