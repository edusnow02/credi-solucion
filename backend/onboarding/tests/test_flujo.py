"""
Tests del flujo completo del onboarding con el OCR FALSO (sin depender de Tesseract):
recibir documentos → encolar → leer → cruzar datos → dejar la solicitud lista para el analista.
"""

import io
from datetime import date
from decimal import Decimal

import pytest
from PIL import Image

from creditos.models import EstadoSolicitud, Solicitud
from nucleo.auditoria import verificar_cadena
from nucleo.models import Cliente, EventoAuditoria, ParametroMensual
from onboarding import servicios, tareas
from onboarding.adaptadores.falso import OCRFalso, resultado_desde_texto
from onboarding.almacenamiento import huella, leer_descifrado
from onboarding.models import CampoExtraido, Documento, EstadoCampo, EstadoDocumento, MotorCampo
from onboarding.puertos import CampoVision, ErrorVision, MotorVision

pytestmark = pytest.mark.django_db

FRENTE = "APELLIDOS\nBENITEZ ORTIZ\nNOMBRES\nANA MARIA\nN.º DE DOCUMENTO\n91.234.567\nFECHA DE NACIMIENTO\n02/03/1990\nSEXO\nFEMENINO"
DORSO = "N.º DE DOCUMENTO\n91.234.567\nFECHA DE VENCIMIENTO\n02/03/2033"
LIQUIDACION = ("EMPLEADOR\nEmpresa Ficticia S.A.\nTRABAJADOR\nANA MARIA BENITEZ ORTIZ\nC.I. N.º\n91.234.567\n"
               "FECHA DE INGRESO\n01/02/2020\nSalario básico G. 5.000.000")


def _png() -> bytes:
    """Una imagen PNG mínima (el OCR falso no la mira, pero el sistema valida que sea una imagen)."""
    salida = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(salida, "PNG")
    return salida.getvalue()


@pytest.fixture(autouse=True)
def ocr_limpio():
    OCRFalso.respuestas = []
    yield
    OCRFalso.respuestas = []


@pytest.fixture
def solicitud():
    """Funcionario público: le piden frente, dorso y liquidación."""
    ParametroMensual.objects.create(mes=date.today(), tasa_maxima_anual=Decimal("0.27"),
                                    tasa_nominal_anual=Decimal("0.25"), pct_max_cuota_ingreso=Decimal("0.30"))
    cliente = Cliente(ci="91234567", nombres="Ana María", apellidos="Benítez Ortiz", segmento="funcionario",
                      sucursal="Luque", canal_origen="telegram")
    cliente.save()
    return Solicitud.objects.create(cliente=cliente, monto_pedido=5_000_000, plazo_meses=12, canal="telegram")


def _mandar(solicitud, **documentos):
    for tipo in documentos:
        servicios.recibir_documento(solicitud, tipo, _png(), "cliente:telegram")


def _procesar(solicitud, respuestas, django_capture_on_commit_callbacks):
    """Las respuestas del OCR falso van en el orden en que se procesan: alfabético por tipo."""
    OCRFalso.respuestas = list(respuestas)
    with django_capture_on_commit_callbacks(execute=True):
        servicios.enviar_a_procesar(solicitud, "cliente:telegram")
    solicitud.refresh_from_db()


def test_flujo_completo_deja_la_solicitud_en_revision(solicitud, django_capture_on_commit_callbacks):
    _mandar(solicitud, ci_frente=1, ci_dorso=1, liquidacion=1)
    # Orden de procesamiento: ci_dorso, ci_frente, liquidacion.
    _procesar(solicitud, [DORSO, FRENTE, LIQUIDACION], django_capture_on_commit_callbacks)

    assert solicitud.estado == EstadoSolicitud.EN_REVISION
    assert solicitud.ingreso_propuesto == 5_000_000
    assert solicitud.cuota_maxima == 1_500_000               # 30 % de 5.000.000
    campos = {(c.documento.tipo, c.nombre): c for c in CampoExtraido.objects.select_related("documento")}
    assert campos[("liquidacion", "empleador")].valor_ocr == "Empresa Ficticia S.A."
    assert campos[("ci_frente", "ci")].estado == EstadoCampo.OK
    # La CI coincide en los tres documentos.
    assert "Coincide en 3" in campos[("ci_dorso", "ci")].observacion or campos[("ci_dorso", "ci")].estado == "ok"
    # Auditoría: recepción, lectura y cambios de estado, con la cadena intacta.
    acciones = list(EventoAuditoria.objects.values_list("accion", flat=True))
    assert acciones.count("documento_recibido") == 3 and acciones.count("documento_procesado") == 3
    assert verificar_cadena()[0]


def test_los_archivos_se_guardan_cifrados_con_su_huella(solicitud, settings):
    contenido = _png()
    documento = servicios.recibir_documento(solicitud, "ci_frente", contenido, "cliente:web")
    en_disco = (settings.MEDIA_ROOT / documento.archivo).read_bytes()
    assert not en_disco.startswith(b"\x89PNG")              # en el disco no hay una imagen legible
    assert leer_descifrado(documento.archivo) == contenido  # pero se recupera igual
    assert documento.sha256 == huella(contenido)


def test_falta_un_documento(solicitud, django_capture_on_commit_callbacks):
    _mandar(solicitud, ci_frente=1, ci_dorso=1)              # falta la liquidación
    _procesar(solicitud, [DORSO, FRENTE], django_capture_on_commit_callbacks)
    assert solicitud.estado == EstadoSolicitud.FALTAN_DOCUMENTOS
    assert servicios.estado_documental(solicitud)["faltantes"] == ["liquidacion"]


def test_documento_ilegible(solicitud, django_capture_on_commit_callbacks):
    _mandar(solicitud, ci_frente=1, ci_dorso=1, liquidacion=1)
    borroso = resultado_desde_texto("D0RS0 ...  l0O", confianza=0.2)
    _procesar(solicitud, [borroso, FRENTE, LIQUIDACION], django_capture_on_commit_callbacks)
    dorso = Documento.objects.get(tipo="ci_dorso")
    assert dorso.estado == EstadoDocumento.ILEGIBLE and "poco legible" in dorso.motivo
    assert solicitud.estado == EstadoSolicitud.FALTAN_DOCUMENTOS
    assert servicios.estado_documental(solicitud)["ilegibles"] == ["ci_dorso"]


def test_ci_que_no_coincide_queda_para_revisar(solicitud, django_capture_on_commit_callbacks):
    _mandar(solicitud, ci_frente=1, ci_dorso=1, liquidacion=1)
    dorso_distinto = DORSO.replace("91.234.567", "91.234.561")
    _procesar(solicitud, [dorso_distinto, FRENTE, LIQUIDACION], django_capture_on_commit_callbacks)
    cis = CampoExtraido.objects.filter(nombre="ci")
    assert all(c.estado == EstadoCampo.REVISAR for c in cis)
    assert solicitud.estado == EstadoSolicitud.EN_REVISION   # el analista decide


def test_reenviar_un_documento_reemplaza_al_anterior(solicitud):
    viejo = servicios.recibir_documento(solicitud, "ci_frente", _png(), "cliente:web")
    nuevo = servicios.recibir_documento(solicitud, "ci_frente", _png(), "cliente:web")
    viejo.refresh_from_db()
    assert viejo.reemplazado and not nuevo.reemplazado
    assert list(servicios.documentos_vigentes(solicitud)) == [nuevo]


@pytest.mark.parametrize("contenido, mensaje", [
    (b"", "vacío"),
    (b"esto no es una imagen", "no es una imagen"),
])
def test_archivos_invalidos(solicitud, contenido, mensaje):
    with pytest.raises(servicios.DocumentoInvalido, match=mensaje):
        servicios.recibir_documento(solicitud, "ci_frente", contenido, "cliente:web")


def test_formato_no_aceptado(solicitud):
    salida = io.BytesIO()
    Image.new("RGB", (10, 10)).save(salida, "GIF")
    with pytest.raises(servicios.DocumentoInvalido, match="Formato no aceptado"):
        servicios.recibir_documento(solicitud, "ci_frente", salida.getvalue(), "cliente:web")


# --- Segunda capa: el motor de visión -------------------------------------------------

class VisionDePrueba(MotorVision):
    disponible = True

    def __init__(self, falla=False):
        self.falla, self.pedidos = falla, []

    def extraer(self, imagen, tipo_mime, tipo_documento, campos):
        self.pedidos.append(campos)
        if self.falla:
            raise ErrorVision("Sin conexión con el servicio de visión.")
        return {c: CampoVision(valor="ANA MARIA", confianza=0.97) for c in campos}


def test_vision_solo_se_consulta_por_campos_dudosos(solicitud, monkeypatch, django_capture_on_commit_callbacks):
    vision = VisionDePrueba()
    monkeypatch.setattr(servicios, "obtener_motor_vision", lambda: vision)
    _mandar(solicitud, ci_frente=1)
    # La línea de los nombres sale con confianza 0,5 (dudosa); el resto, 0,95.
    from onboarding.puertos import PalabraOCR
    frente = resultado_desde_texto(FRENTE)
    frente.palabras = [PalabraOCR(p.texto, 0.5 if p.texto in ("ANA", "MARIA") else p.confianza, p.linea)
                       for p in frente.palabras]
    _procesar(solicitud, [frente], django_capture_on_commit_callbacks)
    assert vision.pedidos == [["nombres"]]                    # no le pregunta lo que ya está claro
    nombres = CampoExtraido.objects.get(nombre="nombres")
    assert nombres.motor == MotorCampo.VISION and nombres.confianza == 0.97


def test_si_la_vision_falla_el_campo_queda_para_revisar(solicitud, monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr(servicios, "obtener_motor_vision", lambda: VisionDePrueba(falla=True))
    _mandar(solicitud, ci_frente=1)
    _procesar(solicitud, [resultado_desde_texto(FRENTE, confianza=0.6)], django_capture_on_commit_callbacks)
    nombres = CampoExtraido.objects.get(nombre="nombres")
    assert nombres.estado == EstadoCampo.REVISAR and "Sin conexión" in nombres.observacion


# --- Selfie, errores y reintentos ----------------------------------------------------------

def test_selfie_usa_verificacion_facial_simulada_y_lo_dice(solicitud, django_capture_on_commit_callbacks):
    _mandar(solicitud, selfie=1)
    _procesar(solicitud, [], django_capture_on_commit_callbacks)
    selfie = Documento.objects.get(tipo="selfie")
    assert selfie.verificacion_facial["simulado"] is True
    assert "SIMULADA" in selfie.verificacion_facial["detalle"]


def test_un_documento_con_error_no_frena_a_los_demas(solicitud, monkeypatch, django_capture_on_commit_callbacks):
    _mandar(solicitud, ci_frente=1, ci_dorso=1)
    original = servicios.procesar_documento

    def fallar_con_dorso(documento, *args):
        if documento.tipo == "ci_dorso":
            raise RuntimeError("falla simulada")
        return original(documento, *args)

    monkeypatch.setattr(servicios, "procesar_documento", fallar_con_dorso)
    _procesar(solicitud, [FRENTE], django_capture_on_commit_callbacks)
    assert Documento.objects.get(tipo="ci_dorso").estado == EstadoDocumento.ERROR
    assert Documento.objects.get(tipo="ci_frente").estado == EstadoDocumento.LEGIBLE


def test_la_tarea_no_procesa_dos_veces(solicitud):
    # La solicitud no está "leyendo documentos": un reintento de la cola no hace nada.
    assert tareas.procesar_solicitud(str(solicitud.id)) == {"omitida": True, "estado": "borrador"}


def test_dos_workers_no_toman_el_mismo_documento(solicitud):
    documento = servicios.recibir_documento(solicitud, "ci_frente", _png(), "cliente:web")
    assert servicios._tomar(documento) is True
    assert servicios._tomar(documento) is False      # el segundo worker no lo puede tomar


def test_un_documento_abandonado_se_puede_retomar(solicitud):
    from django.utils import timezone

    documento = servicios.recibir_documento(solicitud, "ci_frente", _png(), "cliente:web")
    hace_un_rato = timezone.now() - timezone.timedelta(minutes=servicios.MINUTOS_PARA_RETOMAR + 1)
    Documento.objects.filter(pk=documento.pk).update(estado=EstadoDocumento.PROCESANDO, en_proceso_desde=hace_un_rato)
    assert servicios._tomar(documento) is True       # el worker anterior se cayó: se retoma
