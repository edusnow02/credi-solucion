"""
Revisa que la cadena de auditoría esté intacta.

Uso:  python manage.py verificar_auditoria
Sale con código 1 si encuentra un eslabón roto (sirve para automatizarlo).
"""

from django.core.management.base import BaseCommand, CommandError

from nucleo.auditoria import verificar_cadena


class Command(BaseCommand):
    help = "Recalcula las huellas de todos los eventos de auditoría y avisa si la cadena está rota."

    def handle(self, *args, **opciones):
        ok, roto, revisados = verificar_cadena()
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Cadena intacta: {revisados} eventos revisados."))
        else:
            raise CommandError(f"¡Cadena rota en el evento #{roto}! Revisados hasta ahí: {revisados}.")
