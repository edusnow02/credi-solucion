"""
Registro de auditoría encadenado.

Analogía: un libro de actas foliado. Cada acta se escribe con la "huella" del acta anterior.
Si alguien arranca una hoja o cambia una palabra, las huellas dejan de coincidir desde ese punto.

Uso:
    from nucleo.auditoria import registrar
    registrar("usuario:ana", "estado_cambiado", "Solicitud", solicitud.id, {"de": "en_ocr", "a": "en_revision"})
"""

import hashlib
import json
from collections.abc import Iterable

from django.db import connection, transaction
from django.utils import timezone

from nucleo.models import EventoAuditoria

# Huella "anterior" del primer evento: 64 ceros (el libro empieza en blanco).
HASH_INICIAL = "0" * 64

# Número fijo para el candado de PostgreSQL (cualquier número, pero siempre el mismo).
_CANDADO_POSTGRES = 75932025

# Claves que NUNCA pueden ir en 'datos' (datos personales en claro). Es una red de seguridad:
# quien llama a registrar() es responsable de no mandar datos personales con otros nombres.
CLAVES_PROHIBIDAS = {"ci", "nombre", "nombres", "apellidos", "telefono", "correo", "fecha_nacimiento",
                     "empleador", "salario", "ingreso", "ingreso_mensual", "direccion"}


def _contenido(fecha, actor, accion, entidad, entidad_id, datos) -> str:
    """
    Texto canónico de un evento: siempre el mismo orden y formato, para que la huella se pueda
    recalcular igual en cualquier momento (sort_keys ordena las claves del diccionario).
    """
    return json.dumps(
        {
            "fecha": fecha.isoformat(),
            "actor": actor,
            "accion": accion,
            "entidad": entidad,
            "entidad_id": str(entidad_id),
            "datos": datos,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,   # fechas, Decimal y UUID dentro de 'datos' se convierten a texto
    )


def calcular_hash(hash_anterior: str, contenido: str) -> str:
    """huella = SHA-256(huella anterior + contenido)."""
    return hashlib.sha256((hash_anterior + contenido).encode("utf-8")).hexdigest()


def _normalizar_datos(datos: dict) -> dict:
    """Pasa 'datos' por JSON ida y vuelta: así lo que se hashea es exactamente lo que se guarda."""
    return json.loads(json.dumps(datos, default=str, ensure_ascii=False))


def registrar(actor: str, accion: str, entidad: str, entidad_id, datos: dict | None = None) -> EventoAuditoria:
    """Agrega un evento al final de la cadena y lo devuelve."""
    datos = _normalizar_datos(datos or {})
    prohibidas = CLAVES_PROHIBIDAS.intersection(k.lower() for k in datos)
    if prohibidas:
        raise ValueError(f"La auditoría no puede guardar datos personales: {sorted(prohibidas)}")

    # transaction.atomic: o se guarda todo bien, o nada.
    with transaction.atomic():
        if connection.vendor == "postgresql":
            # Candado: dos procesos que registran a la vez hacen fila, así no cuelgan del mismo anterior.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_CANDADO_POSTGRES])
        # (En SQLite las escrituras ya van de a una, no hace falta candado.)
        ultimo = EventoAuditoria.objects.order_by("-id").only("hash").first()
        hash_anterior = ultimo.hash if ultimo else HASH_INICIAL
        fecha = timezone.now()
        contenido = _contenido(fecha, actor, accion, entidad, entidad_id, datos)
        return EventoAuditoria.objects.create(
            fecha=fecha,
            actor=actor,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id),
            datos=datos,
            hash_anterior=hash_anterior,
            hash=calcular_hash(hash_anterior, contenido),
        )


def verificar_cadena(eventos: Iterable[EventoAuditoria] | None = None) -> tuple[bool, int | None, int]:
    """
    Recorre los eventos en orden y recalcula cada huella.

    Devuelve (todo_bien, id_del_primer_evento_roto o None, cantidad_revisada).
    Acepta una lista de eventos para poder probarla en los tests sin tocar la base.
    """
    if eventos is None:
        eventos = EventoAuditoria.objects.order_by("id").iterator()
    esperado_anterior = HASH_INICIAL
    revisados = 0
    for evento in eventos:
        revisados += 1
        contenido = _contenido(evento.fecha, evento.actor, evento.accion, evento.entidad, evento.entidad_id, evento.datos)
        if evento.hash_anterior != esperado_anterior or evento.hash != calcular_hash(evento.hash_anterior, contenido):
            return False, evento.id, revisados
        esperado_anterior = evento.hash
    return True, None, revisados
