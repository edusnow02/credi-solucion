"""
Tests del adaptador de visión con Claude, con un cliente FALSO: no se llama a la API real
(no gasta dinero ni manda datos a ningún lado).
"""

import base64
import json
from types import SimpleNamespace

import pytest

from onboarding.adaptadores.vision_claude import VisionClaude
from onboarding.puertos import ErrorVision


class ClienteFalso:
    """Imita client.beta.messages.create y guarda lo que se le pidió."""

    def __init__(self, respuesta=None, error=None):
        self.pedido, self._respuesta, self._error = None, respuesta, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.pedido = kwargs
        if self._error:
            raise self._error
        return self._respuesta


def _respuesta(datos: dict, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=json.dumps(datos))])


def test_pedido_bien_armado_y_respuesta_interpretada():
    cliente = ClienteFalso(_respuesta({"ci": {"valor": "91234567", "confianza": 0.98},
                                       "nombres": {"valor": "", "confianza": 0.4}}))
    resultado = VisionClaude(modelo="claude-opus-5-5", cliente=cliente).extraer(
        b"\x89PNG-imagen", "image/png", "ci_frente", ["ci", "nombres"])

    assert resultado["ci"].valor == "91234567" and resultado["ci"].confianza == 0.98
    assert resultado["nombres"].valor == "" and resultado["nombres"].confianza == 0   # vacío = confianza 0

    pedido = cliente.pedido
    assert pedido["model"] == "claude-opus-5-5"
    imagen = pedido["messages"][0]["content"][0]
    assert imagen["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(imagen["source"]["data"]) == b"\x89PNG-imagen"
    esquema = pedido["output_config"]["format"]["schema"]
    assert set(esquema["required"]) == {"ci", "nombres"} and esquema["additionalProperties"] is False


def test_confianza_fuera_de_rango_se_limita():
    cliente = ClienteFalso(_respuesta({"ci": {"valor": "1", "confianza": 7}}))
    assert VisionClaude(cliente=cliente).extraer(b"x", "image/png", "ci_dorso", ["ci"])["ci"].confianza == 1.0


@pytest.mark.parametrize("respuesta", [
    _respuesta({}, stop_reason="refusal"),
    _respuesta({}, stop_reason="max_tokens"),
    SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="no es json")]),
])
def test_respuestas_inutilizables_dan_error_de_vision(respuesta):
    with pytest.raises(ErrorVision):
        VisionClaude(cliente=ClienteFalso(respuesta)).extraer(b"x", "image/png", "ci_dorso", ["ci"])


def test_error_de_conexion_da_error_de_vision():
    with pytest.raises(ErrorVision):
        VisionClaude(cliente=ClienteFalso(error=ConnectionError("sin red"))).extraer(b"x", "image/png", "ci_dorso", ["ci"])


def test_sin_campos_no_llama_a_la_api():
    cliente = ClienteFalso()
    assert VisionClaude(cliente=cliente).extraer(b"x", "image/png", "ci_dorso", []) == {}
    assert cliente.pedido is None
