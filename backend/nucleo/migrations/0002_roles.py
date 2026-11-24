"""
Crea los grupos (roles) del personal: analista, cobranzas y gerencia.

Es una migración "de datos": no cambia tablas, agrega filas. Así los roles existen en cualquier
base nueva (tu SQLite, el PostgreSQL de Docker, Render) sin cargarlos a mano.
"""

from django.db import migrations

ROLES = ("analista", "cobranzas", "gerencia")


def crear_roles(apps, schema_editor):
    # apps.get_model: la versión del modelo de ESTA migración (no la actual del código).
    Group = apps.get_model("auth", "Group")
    for nombre in ROLES:
        Group.objects.get_or_create(name=nombre)


def borrar_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("nucleo", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(crear_roles, borrar_roles)]
