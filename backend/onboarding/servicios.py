"""
Servicios del onboarding: las operaciones que usan los canales (Fase 3), el panel (Parte 2C) y la app.

Flujo:
    recibir_documento(...)      ← el cliente manda una foto (por Telegram, la web o la app)
    enviar_a_procesar(...)      ← "ya mandé todo": la solicitud pasa a "leyendo documentos" y se encola
    tareas.procesar_solicitud   ← el worker lee cada documento, cruza los datos y decide el estado

Ningún canal ni módulo toca Tesseract o Claude: todo pasa por los puertos (adaptadores).
"""

import io
import logging
from datetime import date

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from creditos import reglas
from creditos.models import EstadoSolicitud, Solicitud
from nucleo.auditoria import registrar
from nucleo.models import ParametroMensual
from onboarding import config
from onboarding.adaptadores import obtener_motor_ocr, obtener_motor_vision, obtener_verificacion_facial
from onboarding.almacenamiento import guardar_cifrado, huella, leer_descifrado
from onboarding.extraccion import extraer_campos, sin_tildes
from onboarding.models import CampoExtraido, Documento, EstadoCampo, EstadoDocumento, MotorCampo, TipoDocumento
from onboarding.preprocesado import leer_con_enderezado
from onboarding.puertos import ErrorVision, MotorOCR, MotorVision

log = logging.getLogger(__name__)


class DocumentoInvalido(Exception):
    """El archivo no es una imagen aceptada (formato, tamaño o archivo dañado)."""


# ---------------------------------------------------------------------------
# Recepción
# ---------------------------------------------------------------------------

def _validar_imagen(contenido: bytes) -> str:
    """Comprueba que sea una imagen JPEG o PNG sana y devuelve su tipo MIME."""
    if not contenido:
        raise DocumentoInvalido("El archivo está vacío.")
    if len(contenido) > config.TAMANIO_MAXIMO_BYTES:
        raise DocumentoInvalido("El archivo supera los 10 MB.")
    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            formato = imagen.format
            imagen.verify()   # detecta archivos dañados o que no son imágenes de verdad
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise DocumentoInvalido("El archivo no es una imagen válida.") from error
    if formato not in config.FORMATOS_ACEPTADOS:
        raise DocumentoInvalido(f"Formato no aceptado ({formato}). Enviá una foto JPG o PNG.")
    return config.FORMATOS_ACEPTADOS[formato]


def recibir_documento(solicitud: Solicitud, tipo: str, contenido: bytes, actor: str) -> Documento:
    """Guarda el archivo cifrado, registra su huella y deja constancia en la auditoría."""
    tipo = TipoDocumento(tipo)   # error claro si el tipo no existe
    tipo_mime = _validar_imagen(contenido)
    sha256 = huella(contenido)
    with transaction.atomic():
        # Si ya había uno del mismo tipo, queda "reemplazado" (no se borra: trazabilidad).
        Documento.objects.filter(solicitud=solicitud, tipo=tipo, reemplazado=False).update(reemplazado=True)
        documento = Documento(solicitud=solicitud, tipo=tipo, sha256=sha256, tipo_mime=tipo_mime,
                              tamanio_bytes=len(contenido))
        extension = "jpg" if tipo_mime == "image/jpeg" else "png"
        documento.archivo = f"documentos/{solicitud.id}/{documento.id}.{extension}.cifrado"
        guardar_cifrado(contenido, documento.archivo)
        documento.save()
        registrar(actor, "documento_recibido", "Documento", documento.id,
                  {"solicitud": str(solicitud.id), "tipo": tipo.value, "sha256": sha256, "bytes": len(contenido)})
    return documento


def documentos_vigentes(solicitud: Solicitud):
    """Los documentos que cuentan (el último de cada tipo)."""
    return solicitud.documentos.filter(reemplazado=False)


def estado_documental(solicitud: Solicitud) -> dict:
    """Qué falta, qué hay que reenviar y qué se recibió, según el segmento del cliente."""
    requeridos = config.DOCUMENTOS_REQUERIDOS.get(solicitud.cliente.segmento, ["ci_frente", "ci_dorso"])
    vigentes = {d.tipo: d for d in documentos_vigentes(solicitud)}
    return {
        "requeridos": requeridos,
        "faltantes": [t for t in requeridos if t not in vigentes],
        "ilegibles": [t for t, d in vigentes.items() if d.estado == EstadoDocumento.ILEGIBLE],
        "recibidos": sorted(vigentes),
    }


def enviar_a_procesar(solicitud: Solicitud, actor: str) -> None:
    """
    Pasa la solicitud a "leyendo documentos" y encola la lectura. La tarea se encola recién cuando
    la transacción se confirma (on_commit): así el worker nunca busca algo que todavía no se guardó.
    """
    solicitud.cambiar_estado(EstadoSolicitud.EN_OCR, actor)
    transaction.on_commit(lambda: _encolar(solicitud.id))


def _encolar(solicitud_id) -> None:
    from django_q.tasks import async_task   # import local: django_q necesita Django ya configurado
    async_task("onboarding.tareas.procesar_solicitud", str(solicitud_id), task_name=f"ocr-{solicitud_id}")


# ---------------------------------------------------------------------------
# Procesamiento (lo llama la tarea de la cola)
# ---------------------------------------------------------------------------

def procesar_documento(documento: Documento, motor_ocr: MotorOCR, motor_vision: MotorVision, hoy: date) -> None:
    """Lee un documento, extrae sus campos y los guarda con su confianza y su estado."""
    umbral = settings.ONBOARDING["UMBRAL_CONFIANZA"]
    contenido = leer_descifrado(documento.archivo)

    if documento.tipo == TipoDocumento.SELFIE:
        # La selfie no se lee: pasa por la verificación facial (hoy SIMULADA, y queda dicho).
        frente = documentos_vigentes(documento.solicitud).filter(tipo=TipoDocumento.CI_FRENTE).first()
        resultado = obtener_verificacion_facial().comparar(contenido, leer_descifrado(frente.archivo) if frente else None)
        documento.verificacion_facial = {"simulado": resultado.simulado, "coincide": resultado.coincide,
                                         "detalle": resultado.detalle}
        _cerrar(documento, EstadoDocumento.LEGIBLE, confianza=None, texto="", motivo="")
        return

    with Image.open(io.BytesIO(contenido)) as imagen:
        lectura, angulo = leer_con_enderezado(motor_ocr, imagen)
    campos = extraer_campos(lectura, documento.tipo, hoy)

    # ¿Ilegible? Sin texto, confianza general muy baja, o ningún campo encontrado.
    motivo = ""
    if not lectura.palabras:
        motivo = "No se encontró texto en la imagen."
    elif lectura.confianza_promedio < settings.ONBOARDING["UMBRAL_ILEGIBLE"]:
        motivo = f"Imagen poco legible (confianza {lectura.confianza_promedio:.0%})."
    elif not any(c.valor for c in campos.values()):
        motivo = "No se reconoció ningún dato del documento."
    if motivo:
        CampoExtraido.objects.filter(documento=documento).delete()
        _cerrar(documento, EstadoDocumento.ILEGIBLE, lectura.confianza_promedio, lectura.texto, motivo)
        return

    # Segunda capa: el motor de visión, SOLO para los campos dudosos y solo si está activado.
    dudosos = [nombre for nombre, c in campos.items() if c.confianza < umbral]
    vision, nota_vision = {}, ""
    if dudosos and motor_vision.disponible:
        try:
            vision = motor_vision.extraer(contenido, documento.tipo_mime, documento.tipo, dudosos)
        except ErrorVision as error:
            nota_vision = str(error)[:200]
            log.warning("Motor de visión no disponible para %s: %s", documento.id, error)

    CampoExtraido.objects.filter(documento=documento).delete()   # si se reprocesa, no duplicar
    for nombre, leido in campos.items():
        valor, confianza, motor = leido.valor, leido.confianza, motor_ocr.nombre
        propuesta = vision.get(nombre)
        if propuesta and propuesta.valor and propuesta.confianza > confianza:
            valor, confianza, motor = propuesta.valor, propuesta.confianza, MotorCampo.VISION
        if not valor:
            estado = EstadoCampo.NO_ENCONTRADO
        else:
            estado = EstadoCampo.OK if confianza >= umbral else EstadoCampo.REVISAR
        CampoExtraido.objects.create(
            documento=documento, nombre=nombre, valor_ocr=valor, confianza=round(confianza, 4),
            motor=motor, estado=estado, observacion=nota_vision if nombre in dudosos else "",
        )
    _cerrar(documento, EstadoDocumento.LEGIBLE, lectura.confianza_promedio, lectura.texto, "", angulo=angulo)


def _cerrar(documento: Documento, estado: str, confianza, texto: str, motivo: str, angulo: int = 0) -> None:
    documento.estado = estado
    documento.confianza_global = round(confianza, 4) if confianza is not None else None
    documento.texto_ocr = texto
    documento.motivo = motivo
    documento.procesado = timezone.now()
    documento.save()
    revisar = documento.campos.exclude(estado=EstadoCampo.OK).count()
    registrar("sistema", "documento_procesado", "Documento", documento.id, {
        "tipo": documento.tipo, "estado": estado, "confianza_global": documento.confianza_global,
        "campos_a_revisar": revisar, "angulo": angulo,
    })


# ---------------------------------------------------------------------------
# Cruce entre documentos
# ---------------------------------------------------------------------------

def _comparable(valor: str) -> str:
    return " ".join(sin_tildes(valor).upper().split())


def cruzar_documentos(solicitud: Solicitud) -> list[str]:
    """
    Compara los datos repetidos entre documentos (CI, nombre, salario).
    - Si coinciden en dos o más documentos: lectura confirmada → el campo pasa a "ok".
    - Si no coinciden: todos esos campos pasan a "revisar" con una observación.
    Devuelve la lista de alertas para el analista.
    """
    umbral = settings.ONBOARDING["UMBRAL_CONFIANZA"]
    campos = list(CampoExtraido.objects.filter(documento__solicitud=solicitud, documento__reemplazado=False)
                  .select_related("documento"))
    alertas = []

    def cruzar(nombre_campo: str, grupo: list[CampoExtraido], valor_de) -> None:
        con_valor = [c for c in grupo if c.valor_ocr]
        if len(con_valor) < 2:
            return
        valores = {valor_de(c) for c in con_valor}
        if len(valores) == 1:
            for c in con_valor:
                if c.estado != EstadoCampo.OK:
                    # Dos lecturas independientes que coinciden son evidencia fuerte.
                    c.estado, c.confianza = EstadoCampo.OK, max(c.confianza, umbral)
                    c.observacion = f"Coincide en {len(con_valor)} documentos."
                    c.save(update_fields=["estado", "confianza", "observacion"])
        else:
            tipos = ", ".join(sorted(c.documento.get_tipo_display() for c in con_valor))
            alertas.append(f"El dato '{nombre_campo}' no coincide entre: {tipos}.")
            for c in con_valor:
                c.estado = EstadoCampo.REVISAR
                c.observacion = "No coincide con otros documentos."
                c.save(update_fields=["estado", "observacion"])

    cruzar("CI", [c for c in campos if c.nombre == "ci"], lambda c: c.valor_ocr)
    cruzar("salario", [c for c in campos if c.nombre == "salario"], lambda c: c.valor_ocr)

    # Nombre: el frente lo trae partido (nombres + apellidos); la liquidación y el IPS, completo.
    por_doc = {}
    for c in campos:
        por_doc.setdefault(c.documento_id, {})[c.nombre] = c
    nombres = []
    for valores in por_doc.values():
        if "nombre" in valores:
            nombres.append((_comparable(valores["nombre"].valor_ocr), [valores["nombre"]]))
        elif "nombres" in valores and "apellidos" in valores:
            completo = f"{valores['nombres'].valor_ocr} {valores['apellidos'].valor_ocr}"
            nombres.append((_comparable(completo), [valores["nombres"], valores["apellidos"]]))
    nombres = [(n, cs) for n, cs in nombres if n]
    if len({n for n, _ in nombres}) > 1:
        alertas.append("El nombre no coincide entre los documentos.")
        for _, cs in nombres:
            for c in cs:
                c.estado, c.observacion = EstadoCampo.REVISAR, "El nombre no coincide con otros documentos."
                c.save(update_fields=["estado", "observacion"])
    return alertas


def ingreso_propuesto(solicitud: Solicitud) -> int | None:
    """El salario leído con más confianza (liquidación o extracto de IPS)."""
    mejor = (CampoExtraido.objects.filter(documento__solicitud=solicitud, documento__reemplazado=False,
                                          nombre="salario").exclude(valor_ocr="").order_by("-confianza").first())
    if not mejor:
        return None
    try:
        return int(mejor.valor_ocr)
    except ValueError:
        return None


def finalizar_lectura(solicitud: Solicitud, hoy: date) -> dict:
    """Después de leer: cruza datos, propone ingreso y cuota máxima y decide el estado."""
    alertas = cruzar_documentos(solicitud)
    solicitud.ingreso_propuesto = ingreso_propuesto(solicitud)
    parametro = ParametroMensual.vigente(hoy)
    ingreso = solicitud.ingreso_confirmado or solicitud.ingreso_propuesto
    if ingreso and parametro:
        solicitud.cuota_maxima = reglas.cuota_maxima(ingreso, parametro.pct_max_cuota_ingreso)
    solicitud.save(update_fields=["ingreso_propuesto", "cuota_maxima", "actualizada"])

    estado_docs = estado_documental(solicitud)
    if estado_docs["faltantes"] or estado_docs["ilegibles"]:
        solicitud.cambiar_estado(EstadoSolicitud.FALTAN_DOCUMENTOS, "sistema")
    else:
        solicitud.cambiar_estado(EstadoSolicitud.EN_REVISION, "sistema")
    return {"alertas": alertas, **estado_docs}


# Un documento "procesando" desde hace más que esto se considera abandonado (el worker se cayó).
MINUTOS_PARA_RETOMAR = 5


def _tomar(documento: Documento) -> bool:
    """
    "Toma" el documento para procesarlo, con una sola sentencia UPDATE condicional.
    Si dos workers intentan tomar el mismo documento a la vez, solo a uno le devuelve 1 fila.
    Así no hace falta mantener la base bloqueada mientras corre el OCR (que tarda segundos).
    """
    ahora = timezone.now()
    abandonado = ahora - timezone.timedelta(minutes=MINUTOS_PARA_RETOMAR)
    tomados = (Documento.objects.filter(pk=documento.pk)
               .filter(models.Q(estado__in=[EstadoDocumento.RECIBIDO, EstadoDocumento.ERROR])
                       | models.Q(estado=EstadoDocumento.PROCESANDO, en_proceso_desde__lt=abandonado))
               .update(estado=EstadoDocumento.PROCESANDO, en_proceso_desde=ahora))
    return tomados == 1


def procesar_solicitud(solicitud: Solicitud, hoy: date | None = None) -> dict:
    """Lee todos los documentos pendientes de una solicitud y la deja lista para el analista."""
    hoy = hoy or timezone.localdate()
    motor_ocr, motor_vision = obtener_motor_ocr(), obtener_motor_vision()
    for documento in documentos_vigentes(solicitud).exclude(
            estado__in=[EstadoDocumento.LEGIBLE, EstadoDocumento.ILEGIBLE]):
        if not _tomar(documento):
            continue   # lo está procesando otro worker
        documento.refresh_from_db()
        try:
            with transaction.atomic():
                procesar_documento(documento, motor_ocr, motor_vision, hoy)
        except Exception as error:   # un documento con problemas no frena a los demás
            log.exception("Error procesando el documento %s", documento.id)
            documento.refresh_from_db()
            documento.estado, documento.motivo = EstadoDocumento.ERROR, f"Error interno: {type(error).__name__}"
            documento.save(update_fields=["estado", "motivo"])
            registrar("sistema", "documento_error", "Documento", documento.id, {"error": type(error).__name__})

    # Cierre: transacción corta con la solicitud bloqueada, y solo si sigue "leyendo documentos"
    # (si dos tareas llegaran hasta acá, la segunda no hace nada).
    with transaction.atomic():
        bloqueada = Solicitud.objects.select_for_update().select_related("cliente").get(pk=solicitud.pk)
        if bloqueada.estado != EstadoSolicitud.EN_OCR:
            return {"omitida": True, "estado": bloqueada.estado}
        return finalizar_lectura(bloqueada, hoy)
