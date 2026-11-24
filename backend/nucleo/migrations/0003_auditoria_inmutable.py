"""
Candado en la propia base de datos: la tabla de auditoría no acepta UPDATE ni DELETE.

Aunque alguien se salte Django y escriba SQL a mano, la base rechaza el cambio.
Funciona en PostgreSQL (producción, Docker) y en SQLite (desarrollo).

Consecuencia práctica: para empezar de cero hay que borrar la base entera
(SQLite: borrar backend/db.sqlite3; Docker: docker compose down -v), no vaciar la tabla.
"""

from django.db import migrations

TABLA = "nucleo_eventoauditoria"

SQLITE_CREAR = [
    f"""CREATE TRIGGER auditoria_sin_update BEFORE UPDATE ON {TABLA}
        BEGIN SELECT RAISE(ABORT, 'La auditoria no se modifica'); END;""",
    f"""CREATE TRIGGER auditoria_sin_delete BEFORE DELETE ON {TABLA}
        BEGIN SELECT RAISE(ABORT, 'La auditoria no se borra'); END;""",
]
SQLITE_BORRAR = ["DROP TRIGGER IF EXISTS auditoria_sin_update;", "DROP TRIGGER IF EXISTS auditoria_sin_delete;"]

POSTGRES_CREAR = [
    """CREATE OR REPLACE FUNCTION auditoria_inmutable() RETURNS trigger AS $$
       BEGIN
           RAISE EXCEPTION 'La auditoria no se modifica ni se borra';
       END;
       $$ LANGUAGE plpgsql;""",
    # Fila por fila: UPDATE y DELETE.
    f"""CREATE TRIGGER auditoria_sin_cambios BEFORE UPDATE OR DELETE ON {TABLA}
        FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();""",
    # TRUNCATE (vaciar la tabla de golpe) no pasa por las filas: necesita su propio candado.
    f"""CREATE TRIGGER auditoria_sin_vaciar BEFORE TRUNCATE ON {TABLA}
        FOR EACH STATEMENT EXECUTE FUNCTION auditoria_inmutable();""",
]
POSTGRES_BORRAR = [
    f"DROP TRIGGER IF EXISTS auditoria_sin_vaciar ON {TABLA};",
    f"DROP TRIGGER IF EXISTS auditoria_sin_cambios ON {TABLA};",
    "DROP FUNCTION IF EXISTS auditoria_inmutable();",
]


def _ejecutar(schema_editor, sentencias_por_motor: dict) -> None:
    """Ejecuta las sentencias del motor de base de datos que se esté usando."""
    sentencias = sentencias_por_motor.get(schema_editor.connection.vendor)
    if sentencias is None:
        raise RuntimeError(f"Motor de base de datos no soportado: {schema_editor.connection.vendor}")
    for sql in sentencias:
        schema_editor.execute(sql)


def crear_candados(apps, schema_editor):
    _ejecutar(schema_editor, {"sqlite": SQLITE_CREAR, "postgresql": POSTGRES_CREAR})


def quitar_candados(apps, schema_editor):
    _ejecutar(schema_editor, {"sqlite": SQLITE_BORRAR, "postgresql": POSTGRES_BORRAR})


class Migration(migrations.Migration):
    dependencies = [("nucleo", "0002_roles")]

    operations = [migrations.RunPython(crear_candados, quitar_candados)]
