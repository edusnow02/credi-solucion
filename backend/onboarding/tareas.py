"""
Tareas de la cola (las ejecuta el worker de django-q2: python manage.py qcluster).

Analogía del mostrador de la fiambrería: el cliente sacó número (la tarea quedó en la fila) y se fue;
la cocina (el worker) la toma cuando puede. Si la cocina se cae a mitad, django-q2 la reintenta.

Reciben el id como TEXTO (no el objeto): la tarea viaja por la base de datos y tiene que poder
reconstruirse en otro proceso.
"""

from creditos.models import EstadoSolicitud, Solicitud
from onboarding import servicios


def procesar_solicitud(solicitud_id: str) -> dict:
    solicitud = Solicitud.objects.select_related("cliente").get(pk=solicitud_id)
    if solicitud.estado != EstadoSolicitud.EN_OCR:
        # Ya la procesó otra tarea (o el analista la movió): no hacer nada dos veces.
        return {"omitida": True, "estado": solicitud.estado}
    # Sin una transacción larga: cada documento se "toma" y se guarda por separado
    # (ver servicios._tomar), así el OCR, que tarda, no deja la base bloqueada.
    return servicios.procesar_solicitud(solicitud)
