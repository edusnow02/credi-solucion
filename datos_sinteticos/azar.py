"""
Ayudas para elegir al azar de forma reproducible.

Todo el generador usa UN objeto random.Random creado con la semilla. Nunca se usa el módulo
random "global": así la misma semilla da siempre los mismos datos (como barajar igual cada vez).
"""

import random


def elegir_con_peso(rng: random.Random, opciones: dict):
    """
    Elige una clave de un diccionario {opción: peso}.
    Ejemplo: {"a": 0.7, "b": 0.3} → "a" sale 7 de cada 10 veces.
    """
    claves = list(opciones.keys())
    pesos = list(opciones.values())
    # choices devuelve una lista; pedimos un solo elemento (k=1) y lo sacamos.
    return rng.choices(claves, weights=pesos, k=1)[0]


def redondear_a_mil(valor: float) -> int:
    """Redondea guaraníes a miles (los sueldos y montos suelen expresarse así)."""
    return int(round(valor / 1000.0)) * 1000
