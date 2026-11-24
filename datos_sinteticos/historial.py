"""
Genera los créditos, sus cuotas y 24 meses de pagos con mora.

Modelo de mora (todo SUPUESTO, parámetros en supuestos.py; explicación en docs/datos-sinteticos.md):

1. Cada cliente tiene un "riesgo mensual": la probabilidad de no pagar la cuota de un mes estando
   al día. Sale del segmento, la carga de la cuota sobre el ingreso, la antigüedad laboral, un
   factor personal al azar y las anomalías sembradas (cosecha y sucursal). NO depende del sexo;
   de la edad solo si se activa --sesgo-edad.
2. Mes a mes, en cada vencimiento:
   - Si estaba al día: paga (en fecha o con unos días de atraso) o no paga → empieza a deber.
   - Si ya debía k cuotas: se pone al día, paga una (frena la caída) o no paga nada (se hunde).
3. Con CUOTAS_PARA_CASTIGO cuotas adeudadas, el crédito se castiga y no se generan más pagos.

Se generan TODOS los pagos, también los puntuales (idea del Cadastro Positivo).
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

# Las cuotas se calculan con la calculadora oficial del backend (una sola regla en todo el sistema).
from creditos.reglas import cronograma, cuota_francesa, sumar_meses, tasa_mensual_desde_nominal_anual
from datos_sinteticos import supuestos
from datos_sinteticos.azar import elegir_con_peso
from datos_sinteticos.personas import Persona


@dataclass
class CuotaSintetica:
    credito_id: str
    numero: int
    vencimiento: date
    capital: int
    interes: int
    total: int
    estado: str = "pendiente"        # pendiente | pagada | atrasada (al corte)
    fecha_pago: date | None = None
    dias_atraso: int = 0              # días de atraso al pagar, o al corte si sigue impaga


@dataclass
class PagoSintetico:
    id: str
    credito_id: str
    cuota_numero: int
    fecha: date
    monto: int
    medio: str
    dias_atraso: int                  # 0 = pagado en fecha o antes


@dataclass
class CreditoSintetico:
    id: str
    cliente_id: str
    monto: int
    plazo_meses: int
    tasa_nominal_anual: Decimal
    cuota: int
    fecha_desembolso: date
    cosecha: str                      # "AAAA-MM" del desembolso
    sucursal: str
    segmento: str
    canal: str
    cuota_ingreso: Decimal            # cuota / ingreso al aprobar
    estado: str = "vigente"           # vigente | en_mora | cancelado | castigado
    cuotas: list[CuotaSintetica] = field(default_factory=list)
    pagos: list[PagoSintetico] = field(default_factory=list)
    # Riesgo usado por la simulación. Es la "respuesta del guion": NO se exporta a los CSV,
    # para que el score de la Fase 5 no pueda hacer trampa leyéndolo.
    riesgo_mensual: float = 0.0


# ---------------------------------------------------------------------------
# Elección de condiciones
# ---------------------------------------------------------------------------

def _mes_de_desembolso(rng: random.Random) -> tuple[int, date]:
    """
    Elige uno de los 24 meses de historia (0 = el más viejo) y un día dentro de él.
    Los meses recientes pesan un poco más (SUPUESTO: la cartera crece).
    """
    pesos = {m: 1 + 0.03 * m for m in range(supuestos.MESES_HISTORIA)}
    m = elegir_con_peso(rng, pesos)
    # Primer día del mes m, contando hacia atrás desde el mes de corte.
    primer_dia_corte = supuestos.FECHA_CORTE.replace(day=1)
    inicio_mes = sumar_meses(primer_dia_corte, m - (supuestos.MESES_HISTORIA - 1))
    fecha = inicio_mes.replace(day=rng.randint(1, 28))
    # Nunca después del corte (puede pasar en el último mes).
    return m, min(fecha, supuestos.FECHA_CORTE)


def _canal(rng: random.Random, m: int) -> str:
    """Canal de origen: los pesos se mueven en línea recta del inicio al fin de la historia."""
    t = m / (supuestos.MESES_HISTORIA - 1)   # 0 al principio, 1 al final
    pesos = {c: (1 - t) * supuestos.CANALES_INICIO[c] + t * supuestos.CANALES_FIN[c] for c in supuestos.CANALES_INICIO}
    return elegir_con_peso(rng, pesos)


def _monto_y_plazo(rng: random.Random, ingreso: int, tasa_mensual: Decimal) -> tuple[int, int, int]:
    """
    Elige monto y plazo y los ajusta para que la cuota no supere el límite histórico de
    cuota/ingreso, como haría un analista: primero alarga el plazo, después baja el monto.
    Devuelve (monto, plazo, cuota).
    """
    monto = elegir_con_peso(rng, supuestos.MONTOS)
    plazo = elegir_con_peso(rng, supuestos.PLAZOS)
    plazos_ordenados = sorted(supuestos.PLAZOS)
    limite = Decimal(ingreso) * supuestos.CUOTA_INGRESO_MAXIMA_HISTORICA

    while True:
        cuota = cuota_francesa(monto, tasa_mensual, plazo)
        if cuota <= limite:
            return monto, plazo, cuota
        mas_largos = [p for p in plazos_ordenados if p > plazo]
        if mas_largos:
            plazo = mas_largos[0]          # probamos con el plazo siguiente
        elif monto > 500_000:
            monto -= 500_000               # ya con el plazo máximo: bajamos el monto
        else:
            return monto, plazo, cuota     # caso extremo: se otorga el mínimo


def _riesgo_mensual(rng: random.Random, persona: Persona, cuota_ingreso: Decimal, cosecha: str,
                    sucursal: str, fecha_desembolso: date, sesgo_edad: bool) -> float:
    """Probabilidad mensual de no pagar estando al día (ver docstring del módulo)."""
    riesgo = supuestos.SEGMENTOS[persona.segmento]["riesgo_base"]
    # Carga financiera: más cuota sobre ingreso, más riesgo.
    riesgo *= 1 + supuestos.EFECTO_CUOTA_INGRESO * float(cuota_ingreso)
    # Antigüedad laboral baja (solo si tiene empleador).
    antiguedad = persona.antiguedad_meses_en(fecha_desembolso)
    if antiguedad is not None and antiguedad < supuestos.ANTIGUEDAD_BAJA_MESES:
        riesgo *= supuestos.MULTIPLICADOR_ANTIGUEDAD_BAJA
    # Factor personal log-normal con media 1 (mu = -sigma²/2 hace que el promedio sea 1).
    sigma = supuestos.DISPERSION_RIESGO
    riesgo *= rng.lognormvariate(-sigma * sigma / 2, sigma)
    # Anomalías sembradas para el dashboard.
    riesgo *= supuestos.COSECHAS_ANOMALAS.get(cosecha, 1.0)
    riesgo *= supuestos.SUCURSALES_ANOMALAS.get(sucursal, 1.0)
    # Sesgo por edad, solo si se pidió explícitamente.
    if sesgo_edad and persona.edad_en(fecha_desembolso) < supuestos.SESGO_EDAD_LIMITE:
        riesgo *= supuestos.SESGO_EDAD_MULTIPLICADOR
    return min(riesgo, supuestos.RIESGO_MAXIMO)


# ---------------------------------------------------------------------------
# Simulación de pagos
# ---------------------------------------------------------------------------

def _registrar_pago(rng: random.Random, credito: CreditoSintetico, cuota: CuotaSintetica, fecha: date) -> bool:
    """
    Marca la cuota como pagada en 'fecha' y crea el Pago. Si la fecha cae después del corte,
    el pago todavía no ocurrió: no se registra y devuelve False.
    """
    if fecha > supuestos.FECHA_CORTE:
        return False
    cuota.estado = "pagada"
    cuota.fecha_pago = fecha
    cuota.dias_atraso = max((fecha - cuota.vencimiento).days, 0)
    credito.pagos.append(
        PagoSintetico(
            id=f"{credito.id}-P{len(credito.pagos) + 1:02d}",
            credito_id=credito.id,
            cuota_numero=cuota.numero,
            fecha=fecha,
            monto=cuota.total,
            medio=elegir_con_peso(rng, supuestos.MEDIOS_PAGO),
            dias_atraso=cuota.dias_atraso,
        )
    )
    return True


def _simular_pagos(rng: random.Random, credito: CreditoSintetico) -> None:
    """Recorre los vencimientos hasta el corte y decide qué paga el cliente cada mes."""
    adeudadas: list[CuotaSintetica] = []   # cuotas vencidas e impagas, de la más vieja a la más nueva
    castigado = False
    p = credito.riesgo_mensual

    for cuota in credito.cuotas:
        if cuota.vencimiento > supuestos.FECHA_CORTE or castigado:
            break
        adeudadas.append(cuota)

        if len(adeudadas) == 1:
            # Estaba al día: paga la cuota del mes con probabilidad (1 − riesgo).
            if rng.random() >= p:
                if rng.random() < supuestos.PROB_PAGO_PUNTUAL:
                    fecha = cuota.vencimiento - timedelta(days=rng.randint(0, 5))
                    fecha = max(fecha, credito.fecha_desembolso)
                else:
                    fecha = cuota.vencimiento + timedelta(days=rng.randint(*supuestos.ATRASO_LEVE_DIAS))
                if _registrar_pago(rng, credito, cuota, fecha):
                    adeudadas.clear()
        else:
            # Ya debía cuotas: k = cuántas debía ANTES de este vencimiento (tope 5 para la tabla).
            k = min(len(adeudadas) - 1, 5)
            azar = rng.random()
            fecha = cuota.vencimiento + timedelta(days=rng.randint(0, 20))
            if azar < supuestos.PROB_PONERSE_AL_DIA[k]:
                # Se pone al día: paga todas las adeudadas el mismo día.
                pagadas = [c for c in adeudadas if _registrar_pago(rng, credito, c, fecha)]
                adeudadas = [c for c in adeudadas if c not in pagadas]
            elif azar < supuestos.PROB_PONERSE_AL_DIA[k] + supuestos.PROB_PAGAR_UNA[k]:
                # Paga solo la más vieja.
                if _registrar_pago(rng, credito, adeudadas[0], fecha):
                    adeudadas.pop(0)
            # Si no, no paga nada este mes.

        if len(adeudadas) >= supuestos.CUOTAS_PARA_CASTIGO:
            castigado = True

    # Estado de cada cuota al corte.
    for cuota in credito.cuotas:
        if cuota.estado != "pagada" and cuota.vencimiento <= supuestos.FECHA_CORTE:
            cuota.estado = "atrasada"
            cuota.dias_atraso = (supuestos.FECHA_CORTE - cuota.vencimiento).days

    # Estado del crédito al corte.
    if castigado:
        credito.estado = "castigado"
    elif all(c.estado == "pagada" for c in credito.cuotas):
        credito.estado = "cancelado"
    elif any(c.estado == "atrasada" for c in credito.cuotas):
        credito.estado = "en_mora"
    else:
        credito.estado = "vigente"


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def generar_creditos(rng: random.Random, personas: list[Persona], sesgo_edad: bool = False) -> list[CreditoSintetico]:
    """Un crédito por cliente (simplificación: sin renovaciones), con cuotas y pagos hasta el corte."""
    tasa_mensual = tasa_mensual_desde_nominal_anual(supuestos.TASA_NOMINAL_ANUAL)
    creditos = []
    for indice, persona in enumerate(personas, start=1):
        m, fecha_desembolso = _mes_de_desembolso(rng)
        monto, plazo, cuota = _monto_y_plazo(rng, persona.ingreso_mensual, tasa_mensual)
        cuota_ingreso = (Decimal(cuota) / Decimal(persona.ingreso_mensual)).quantize(Decimal("0.0001"))
        cosecha = fecha_desembolso.strftime("%Y-%m")
        credito = CreditoSintetico(
            id=f"K{indice:05d}",
            cliente_id=persona.id,
            monto=monto,
            plazo_meses=plazo,
            tasa_nominal_anual=supuestos.TASA_NOMINAL_ANUAL,
            cuota=cuota,
            fecha_desembolso=fecha_desembolso,
            cosecha=cosecha,
            sucursal=persona.sucursal,
            segmento=persona.segmento,
            canal=_canal(rng, m),
            cuota_ingreso=cuota_ingreso,
        )
        credito.riesgo_mensual = _riesgo_mensual(
            rng, persona, cuota_ingreso, cosecha, persona.sucursal, fecha_desembolso, sesgo_edad
        )
        # Cronograma con la calculadora oficial.
        credito.cuotas = [
            CuotaSintetica(credito.id, c.numero, c.vencimiento, c.capital, c.interes, c.total)
            for c in cronograma(monto, tasa_mensual, plazo, fecha_desembolso)
        ]
        _simular_pagos(rng, credito)
        creditos.append(credito)
    return creditos


def dias_atraso_al_corte(credito: CreditoSintetico) -> int:
    """Días de atraso de la cuota impaga más vieja al corte (0 si está al día)."""
    atrasadas = [c.dias_atraso for c in credito.cuotas if c.estado == "atrasada"]
    return max(atrasadas, default=0)


def tasa_mora_30(creditos: list[CreditoSintetico]) -> float:
    """
    Proporción de créditos NO cancelados con más de 30 días de atraso al corte
    (incluye castigados). Si no hay créditos activos, devuelve 0.
    """
    activos = [c for c in creditos if c.estado != "cancelado"]
    if not activos:
        return 0.0
    en_mora = sum(1 for c in activos if dias_atraso_al_corte(c) > 30)
    return en_mora / len(activos)


def mora_temprana(creditos: list[CreditoSintetico], cuotas: int = 6) -> float:
    """
    Proporción de créditos en los que alguna de las primeras 'cuotas' llegó a más de 30 días
    de atraso (pagada tarde o todavía impaga). Solo cuenta créditos que ya tuvieron esas cuotas
    vencidas al corte, así todas las cosechas se comparan a la misma "edad".

    Analogía: comparar cosechas de soja midiendo todas a los 6 meses de sembradas, no el mismo día.
    """
    maduros = [c for c in creditos
               if len(c.cuotas) >= cuotas and c.cuotas[cuotas - 1].vencimiento <= supuestos.FECHA_CORTE]
    if not maduros:
        return 0.0
    malos = sum(1 for c in maduros if any(q.dias_atraso > 30 for q in c.cuotas[:cuotas]))
    return malos / len(maduros)

