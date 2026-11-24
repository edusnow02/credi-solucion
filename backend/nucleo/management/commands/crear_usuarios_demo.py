"""
Crea los usuarios de demo del personal: analista, cobranzas y gerencia.

Uso:  python manage.py crear_usuarios_demo [--nuevas-contrasenas]

Las contraseñas se generan al azar y se muestran UNA sola vez en la terminal: no se guardan
en ningún archivo del repositorio. Si las perdés, corré de nuevo con --nuevas-contrasenas.
"""

import secrets

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from nucleo import roles
from nucleo.auditoria import registrar


class Command(BaseCommand):
    help = "Crea un usuario por rol (analista, cobranzas, gerencia) con contraseña al azar."

    def add_arguments(self, parser):
        parser.add_argument("--nuevas-contrasenas", action="store_true",
                            help="cambia la contraseña de los usuarios que ya existen")

    def handle(self, *args, **opciones):
        for rol in roles.TODOS:
            usuario, creado = User.objects.get_or_create(username=rol, defaults={"first_name": rol.capitalize()})
            usuario.groups.add(Group.objects.get(name=rol))
            if creado or opciones["nuevas_contrasenas"]:
                # 16 caracteres al azar: cumple el mínimo de 10 y no está en ninguna lista de contraseñas comunes.
                contrasena = secrets.token_urlsafe(12)
                usuario.set_password(contrasena)
                usuario.save()
                registrar("sistema", "usuario_demo_contrasena", "User", usuario.pk, {"rol": rol})
                self.stdout.write(f"  {rol:<10} contraseña: {contrasena}")
            else:
                self.stdout.write(f"  {rol:<10} ya existía (contraseña sin cambios)")
        self.stdout.write(self.style.WARNING("Anotá las contraseñas: no se vuelven a mostrar."))
