"""
Respaldo de visión con Claude (OPCIONAL, apagado por defecto).

Se activa con MOTOR_VISION=claude en el .env y necesita ANTHROPIC_API_KEY y el paquete `anthropic`
(pip install -r backend/requirements-opcional.txt).

AVISO DE DATOS PERSONALES: activar esto envía la imagen de la cédula o la liquidación a un
servicio externo (Anthropic). Antes de usarlo con clientes reales hace falta su consentimiento y
revisar la Ley 7593/2025. Con los datos sintéticos de la demo no hay problema.

Cómo funciona:
- Se manda la imagen en base64 y la lista de campos que se necesitan.
- "Salida estructurada" (output_config.format): Claude responde un JSON que respeta EXACTAMENTE el
  esquema pedido, así no hay que adivinar el formato de la respuesta.
- La confianza que devuelve es AUTODECLARADA por el modelo, no está calibrada: el campo igual lo
  confirma el analista.
- Si Claude rechaza el pedido, hay un error de red o un límite de uso, se lanza ErrorVision y el
  campo queda "para revisar" (nunca se inventa un valor).
"""

import base64
import json

from onboarding.puertos import CampoVision, ErrorVision, MotorVision

# Descripciones de los campos para el pedido (en español, como los documentos).
DESCRIPCION_CAMPOS = {
    "apellidos": "apellidos tal como figuran",
    "nombres": "nombres de pila tal como figuran",
    "nombre": "nombre completo de la persona",
    "ci": "número de cédula de identidad, solo dígitos",
    "fecha_nacimiento": "fecha de nacimiento en formato AAAA-MM-DD",
    "vencimiento": "fecha de vencimiento en formato AAAA-MM-DD",
    "sexo": "F o M",
    "empleador": "nombre del empleador",
    "fecha_ingreso": "fecha de ingreso al empleo en formato AAAA-MM-DD",
    "salario": "salario básico mensual en guaraníes, solo dígitos",
    "antiguedad_meses": "meses de aporte con el empleador actual, solo dígitos",
}

INSTRUCCIONES = (
    "Sos un asistente que lee documentos paraguayos (cédula, liquidación de sueldo, extracto de IPS) "
    "para un analista de crédito. Extraé solo lo que se lee en la imagen. Si un campo no se ve o no "
    "se puede leer con seguridad, devolvé valor vacío y confianza 0. No adivines ni completes datos. "
    "La confianza va de 0 a 1 y refleja qué tan legible es el valor en la imagen."
)


def _esquema(campos: list[str]) -> dict:
    """Esquema JSON de la respuesta: un objeto con {valor, confianza} por cada campo pedido."""
    campo = {
        "type": "object",
        "properties": {"valor": {"type": "string"}, "confianza": {"type": "number"}},
        "required": ["valor", "confianza"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {nombre: campo for nombre in campos},
        "required": list(campos),
        "additionalProperties": False,
    }


class VisionClaude(MotorVision):
    disponible = True

    def __init__(self, modelo: str = "claude-opus-5-5", cliente=None):
        self.modelo = modelo
        self._cliente = cliente   # los tests pasan un cliente falso; en uso real se crea al primer pedido

    def _obtener_cliente(self):
        if self._cliente is None:
            import anthropic   # import tardío: el paquete es opcional
            # Sin argumentos: toma ANTHROPIC_API_KEY del entorno (nunca escribir la clave en el código).
            self._cliente = anthropic.Anthropic()
        return self._cliente

    def extraer(self, imagen: bytes, tipo_mime: str, tipo_documento: str, campos: list[str]) -> dict[str, CampoVision]:
        if not campos:
            return {}
        cliente = self._obtener_cliente()
        lista = "\n".join(f"- {c}: {DESCRIPCION_CAMPOS.get(c, c)}" for c in campos)
        try:
            respuesta = cliente.beta.messages.create(
                model=self.modelo,
                max_tokens=4000,
                system=INSTRUCCIONES,
                # Extracción simple: esfuerzo bajo alcanza y es más rápido y barato.
                # La salida estructurada garantiza un JSON con el esquema pedido.
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": _esquema(campos)}},
                # Si el modelo rechaza el pedido por una política de seguridad, el servidor lo reintenta
                # con un modelo de respaldo (fallbacks), en el mismo pedido.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": tipo_mime,
                            "data": base64.standard_b64encode(imagen).decode("ascii"),
                        }},
                        {"type": "text", "text": f"Documento: {tipo_documento}. Campos a extraer:\n{lista}"},
                    ],
                }],
            )
        except Exception as error:   # errores del SDK: red, límite de uso, clave inválida, etc.
            raise ErrorVision(self._describir_error(error)) from error

        if respuesta.stop_reason == "refusal":
            raise ErrorVision("El modelo de visión rechazó el pedido.")
        if respuesta.stop_reason == "max_tokens":
            raise ErrorVision("La respuesta del modelo de visión quedó cortada.")
        try:
            texto = next(b.text for b in respuesta.content if b.type == "text")
            datos = json.loads(texto)
        except (StopIteration, json.JSONDecodeError) as error:
            raise ErrorVision("La respuesta del modelo de visión no es un JSON válido.") from error

        resultado = {}
        for nombre in campos:
            campo = datos.get(nombre) or {}
            valor = str(campo.get("valor", "")).strip()
            # La confianza se limita a [0, 1] por si el modelo devolviera algo fuera de rango.
            confianza = min(max(float(campo.get("confianza", 0) or 0), 0.0), 1.0)
            resultado[nombre] = CampoVision(valor=valor, confianza=confianza if valor else 0.0)
        return resultado

    @staticmethod
    def _describir_error(error: Exception) -> str:
        """Traduce los errores del SDK a un mensaje claro, sin depender de que el paquete esté instalado."""
        try:
            import anthropic
        except ImportError:
            return f"Error del motor de visión: {error}"
        if isinstance(error, anthropic.AuthenticationError):
            return "Clave de API inválida o ausente (ANTHROPIC_API_KEY)."
        if isinstance(error, anthropic.RateLimitError):
            return "Límite de uso del modelo de visión alcanzado; se reintentará más tarde."
        if isinstance(error, anthropic.APIStatusError):
            return f"El servicio de visión respondió con error {error.status_code}."
        if isinstance(error, anthropic.APIConnectionError):
            return "Sin conexión con el servicio de visión."
        return f"Error del motor de visión: {error}"
