"""
Crea el archivo .env (en la raíz del proyecto) con claves nuevas al azar.

Uso (desde la carpeta backend/, con el entorno virtual activado):
    python crear_env.py

No es un comando de Django a propósito: Django no arranca sin las claves, así que el comando
que las crea tiene que funcionar sin Django (el huevo antes que la gallina).

NUNCA pisa un .env existente: si se perdiera CLAVES_CIFRADO, los datos personales cifrados
quedarían ilegibles para siempre. Guardá una copia del .env fuera del repositorio.
"""

import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / ".env"
EJEMPLO = RAIZ / ".env.example"


def main() -> None:
    if DESTINO.exists():
        sys.exit(f"Ya existe {DESTINO}. No lo piso (perderías la clave de cifrado). Si querés uno nuevo, movelo antes.")

    # Valores nuevos al azar. secrets usa el generador seguro del sistema operativo.
    valores = {
        "SECRET_KEY": secrets.token_urlsafe(50),
        "CLAVES_CIFRADO": Fernet.generate_key().decode(),
        "CLAVE_INDICE": secrets.token_urlsafe(48),
    }

    # Copiamos el ejemplo línea por línea y reemplazamos solo las claves.
    lineas = []
    for linea in EJEMPLO.read_text(encoding="utf-8").splitlines():
        nombre = linea.split("=", 1)[0].strip()
        if nombre in valores and not linea.lstrip().startswith("#"):
            linea = f"{nombre}={valores[nombre]}"
        lineas.append(linea)
    DESTINO.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    DESTINO.chmod(0o600)   # solo tu usuario puede leerlo
    print(f"Listo: {DESTINO} creado con claves nuevas. Guardá una copia en un lugar seguro, fuera del repositorio.")


if __name__ == "__main__":
    main()
