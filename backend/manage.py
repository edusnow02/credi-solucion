#!/usr/bin/env python
"""
Puerta de entrada de los comandos de Django.

Ejemplos (desde la carpeta backend/, con el entorno virtual activado):
    python manage.py migrate              # crea o actualiza las tablas
    python manage.py runserver            # levanta el servidor de desarrollo
    python manage.py cargar_sinteticos    # carga los datos de la Fase 1
"""

import os
import sys


def main() -> None:
    # Le decimos a Django dónde está la configuración (backend/servidor/settings.py).
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "servidor.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
