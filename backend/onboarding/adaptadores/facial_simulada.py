"""
Verificación facial SIMULADA.

No compara caras. Existe para que el flujo de la selfie funcione en la demo y para que la interfaz
pueda decir claramente "verificación simulada". Regla del proyecto: no fingir funciones.
Un proveedor real (comparación de rostro + prueba de vida) se conecta implementando el mismo puerto.
"""

from onboarding.puertos import ResultadoFacial, VerificacionFacial


class VerificacionFacialSimulada(VerificacionFacial):
    def comparar(self, selfie: bytes, foto_ci: bytes | None) -> ResultadoFacial:
        return ResultadoFacial(
            simulado=True,
            coincide=None,
            detalle="Verificación facial SIMULADA: no se comparó la selfie con la cédula.",
        )
