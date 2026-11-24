"""
Cifrado de datos personales en reposo.

Analogía:
- Cifrar es guardar el dato en un cajón con llave (Fernet). Quien robe una copia de la base ve
  texto ilegible; sin la llave (CLAVES_CIFRADO, en el .env) no puede leerlo.
- El índice ciego es una huella digital del dato (HMAC). Sirve para BUSCAR ("¿ya existe esta CI?")
  sin abrir ningún cajón: se calcula la huella de lo que se busca y se compara con las guardadas.
  La huella no permite reconstruir el dato, y sin CLAVE_INDICE tampoco se puede calcular.

Por qué no uso una librería externa: las conocidas para Django (django-fernet-fields y similares)
están abandonadas. Esto son pocas líneas sobre `cryptography`, que sí está mantenida.

Límite importante: un campo cifrado NO se puede filtrar ni ordenar en la base
(Cliente.objects.filter(nombres="Ana") no funciona), porque cada cifrado da un texto distinto.
Para buscar se usa el índice ciego.
"""

import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models


@lru_cache(maxsize=1)
def _llavero() -> MultiFernet:
    """
    Arma el "llavero" con todas las claves. MultiFernet cifra con la primera y prueba todas al
    descifrar: así se puede rotar la clave (agregar una nueva adelante) sin perder lo ya guardado.
    lru_cache: se arma una sola vez, no en cada dato.
    """
    return MultiFernet([Fernet(clave.encode()) for clave in settings.CLAVES_CIFRADO])


def cifrar_texto(texto: str) -> str:
    """Texto → texto cifrado (base64, apto para guardar en una columna de texto)."""
    return _llavero().encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar_texto(cifrado: str) -> str:
    """Texto cifrado → texto original. Si la clave no corresponde, falla con un error claro."""
    try:
        return _llavero().decrypt(cifrado.encode("ascii")).decode("utf-8")
    except InvalidToken as error:
        raise ValueError("No se pudo descifrar: la clave de cifrado no coincide con la de los datos.") from error


def cifrar_bytes(datos: bytes) -> bytes:
    """Para archivos (imágenes de documentos, pagarés)."""
    return _llavero().encrypt(datos)


def descifrar_bytes(datos: bytes) -> bytes:
    try:
        return _llavero().decrypt(datos)
    except InvalidToken as error:
        raise ValueError("No se pudo descifrar el archivo: la clave no coincide.") from error


def normalizar_ci(ci) -> str:
    """'1.234.567' , ' 1234567 ' o 1234567 → '1234567' (solo dígitos, sin ceros a la izquierda)."""
    digitos = re.sub(r"\D", "", str(ci))
    return digitos.lstrip("0") or "0"


def indice_ciego(valor: str, tipo: str) -> str:
    """
    Huella HMAC-SHA256 de un valor ya normalizado.

    'tipo' (por ejemplo "ci") se mezcla en la huella para que la huella de una CI nunca coincida
    con la de otro dato que casualmente tenga los mismos caracteres.
    """
    mensaje = f"{tipo}:{valor}".encode("utf-8")
    return hmac.new(settings.CLAVE_INDICE.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def indice_ci(ci) -> str:
    """Atajo: huella de una CI en cualquier formato."""
    return indice_ciego(normalizar_ci(ci), "ci")


class CampoCifrado(models.TextField):
    """
    Campo de modelo que se guarda cifrado y se lee descifrado, sin que el resto del código lo note.

    - get_prep_value: Python → base. Cifra antes de guardar.
    - from_db_value:  base → Python. Descifra al leer.
    Los valores vacíos ("" o None) se guardan tal cual, para no cifrar la nada.
    """

    description = "Texto cifrado con Fernet"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return cifrar_texto(str(value))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return descifrar_texto(value)
