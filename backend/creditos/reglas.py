"""
Reglas de crédito: el ÚNICO lugar donde se calculan cuotas.

Analogía: es la calculadora oficial de la empresa. El panel, los canales, la app y el generador
de datos sintéticos le preguntan a esta calculadora; nadie hace la cuenta por su lado.
Así, si cambia una regla, cambia en todos lados a la vez.

Reglas de este archivo:
- Funciones PURAS: reciben números y devuelven números. No leen la base de datos ni la hora
  del sistema. Por eso se pueden probar con tests simples.
- Sin Django: así las puede usar el generador de datos (que corre sin servidor).
- Guaraníes siempre como ENTEROS (el guaraní no usa decimales en la práctica).
- Cálculos con Decimal, no con float: float acumula errores de redondeo en las cuentas de dinero.

Contenido:
- Fase 1: cuota del sistema francés y cronograma.
- Fase 2: cargos, costo total, tasa efectiva con cargos, cuota máxima según ingreso, comparación
  con la tasa máxima del mes y con la regla de Apple, y simular() que junta todo.
Los VALORES (tasas, % de cuota, cargos, tope) llegan como argumentos desde ParametroMensual;
acá solo están las fórmulas y las reglas de la tienda de Apple.
"""

# calendar: para saber cuántos días tiene cada mes (al calcular vencimientos).
import calendar
# dataclass: forma corta de definir una "ficha" con campos (como una fila de una tabla).
from dataclasses import dataclass
# date: fechas sin hora.
from datetime import date
# Decimal: números decimales exactos; ROUND_HALF_UP: redondeo "escolar" (0,5 sube).
from decimal import ROUND_HALF_UP, Decimal


# Ficha de una cuota del cronograma. frozen=True la vuelve inmutable (no se puede modificar
# por accidente después de calculada).
@dataclass(frozen=True)
class CuotaCalculada:
    numero: int          # 1, 2, 3, ...
    vencimiento: date    # fecha en que vence
    capital: int         # parte que devuelve lo prestado (G.)
    interes: int         # parte que paga el interés del mes (G.)
    total: int           # capital + interés (G.); los cargos se suman en la Fase 2
    saldo_despues: int   # cuánto se debe de capital después de pagar esta cuota (G.)


def _redondear_guaranies(valor: Decimal) -> int:
    """Redondea un Decimal al guaraní entero más cercano (0,5 sube)."""
    # quantize(Decimal("1")) deja el número sin decimales usando la regla indicada.
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def tasa_mensual_desde_nominal_anual(tasa_nominal_anual: Decimal) -> Decimal:
    """
    Convierte una tasa nominal anual (p. ej. 0,30 = 30 %) en tasa mensual (0,025).

    La tasa NOMINAL se divide por 12. (No confundir con la tasa EFECTIVA, que capitaliza
    mes a mes; esa se calcula en la Fase 2 junto con los cargos.)
    """
    # Convertimos a Decimal por si llega como texto o entero.
    tasa = Decimal(tasa_nominal_anual)
    # Una tasa negativa no tiene sentido en un crédito: avisamos con un error claro.
    if tasa < 0:
        raise ValueError("La tasa no puede ser negativa.")
    return tasa / Decimal(12)


def cuota_francesa(monto: int, tasa_mensual: Decimal, plazo_meses: int) -> int:
    """
    Cuota fija del sistema francés (todas las cuotas iguales).

    Fórmula: cuota = monto × i × (1 + i)^n / ((1 + i)^n − 1)
      monto = capital prestado, i = tasa mensual, n = cantidad de cuotas.

    Analogía: es la cuota que, pagada todos los meses, deja la deuda exactamente en cero
    al final, como una escalera que baja siempre el mismo escalón de pago.
    """
    # Validaciones: datos imposibles se rechazan en lugar de dar un número sin sentido.
    if monto <= 0:
        raise ValueError("El monto tiene que ser mayor que cero.")
    if plazo_meses <= 0:
        raise ValueError("El plazo tiene que ser de al menos un mes.")
    i = Decimal(tasa_mensual)
    if i < 0:
        raise ValueError("La tasa no puede ser negativa.")

    # Caso especial: sin interés, la cuota es simplemente monto / plazo.
    if i == 0:
        return _redondear_guaranies(Decimal(monto) / Decimal(plazo_meses))

    # (1 + i)^n: cuánto crece 1 guaraní en n meses.
    factor = (Decimal(1) + i) ** plazo_meses
    # Aplicamos la fórmula y redondeamos al guaraní.
    cuota = Decimal(monto) * i * factor / (factor - Decimal(1))
    return _redondear_guaranies(cuota)


def sumar_meses(fecha: date, meses: int) -> date:
    """
    Suma meses a una fecha conservando el día; si el mes no tiene ese día, usa el último.
    Ejemplo: 31 de enero + 1 mes = 28 (o 29) de febrero.
    """
    # Pasamos el mes a un contador lineal (año*12 + mes) para sumar sin errores de cambio de año.
    total = fecha.year * 12 + (fecha.month - 1) + meses
    anio, mes = divmod(total, 12)
    mes += 1
    # monthrange devuelve (día de la semana del 1.º, cantidad de días del mes).
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(fecha.day, ultimo_dia))


def cronograma(monto: int, tasa_mensual: Decimal, plazo_meses: int, fecha_desembolso: date) -> list[CuotaCalculada]:
    """
    Arma la tabla de cuotas del sistema francés.

    Cada mes:
      interés = saldo × tasa mensual (redondeado al guaraní)
      capital = cuota − interés
    En la ÚLTIMA cuota el capital se ajusta para que la suma del capital sea EXACTAMENTE el monto
    (los redondeos de cada mes dejan unos pocos guaraníes de diferencia que se absorben ahí).

    La primera cuota vence un mes después del desembolso.
    """
    # La cuota fija sale de la función de arriba (una sola fórmula en todo el sistema).
    cuota = cuota_francesa(monto, tasa_mensual, plazo_meses)
    i = Decimal(tasa_mensual)
    saldo = monto                     # capital que todavía se debe
    cuotas: list[CuotaCalculada] = []

    for numero in range(1, plazo_meses + 1):
        # Interés del mes sobre lo que todavía se debe.
        interes = _redondear_guaranies(Decimal(saldo) * i)
        if numero == plazo_meses:
            # Última cuota: se paga todo el saldo que quede, sin importar el redondeo.
            capital = saldo
        else:
            # Cuotas intermedias: lo que sobra de la cuota después del interés va a capital.
            capital = cuota - interes
        saldo -= capital
        cuotas.append(
            CuotaCalculada(
                numero=numero,
                vencimiento=sumar_meses(fecha_desembolso, numero),
                capital=capital,
                interes=interes,
                total=capital + interes,
                saldo_despues=saldo,
            )
        )
    return cuotas


# ===========================================================================
# Fase 2: cargos, costo total, tasa efectiva, cuota máxima y comparación con topes
# ===========================================================================

# Regla de Apple para apps de préstamos (App Review Guidelines 3.2.2(ix), actualizada en nov 2025).
# FUENTE: https://developer.apple.com/news/?id=ey6d8onl — volver a verificar en la Fase 8.
# Son reglas de la tienda, no de Paraguay: por eso viven acá y no en ParametroMensual.
APPLE_TASA_MAXIMA = Decimal("0.36")      # tasa anual máxima, incluidos costos y cargos
APPLE_PLAZO_MINIMO_DIAS = 60             # no se puede exigir el pago total en 60 días o menos

# Tipos de cargo que entiende la calculadora. Los VALORES de cada cargo vienen de
# ParametroMensual.cargos (hoy SUPUESTO: falta que Credisolución confirme sus cargos reales).
TIPOS_CARGO = {
    "inicial_fijo": "Monto fijo cobrado al desembolsar (se descuenta de lo que recibe el cliente)",
    "inicial_pct": "Porcentaje del monto cobrado al desembolsar (se descuenta)",
    "mensual_fijo": "Monto fijo sumado a cada cuota",
    "pct_interes": "Porcentaje sobre el interés de cada cuota (por ejemplo, un impuesto sobre intereses)",
    "pct_saldo": "Porcentaje mensual sobre el saldo de capital (por ejemplo, un seguro)",
}


@dataclass(frozen=True)
class Cargo:
    concepto: str
    tipo: str          # una clave de TIPOS_CARGO
    valor: Decimal     # guaraníes si es fijo; proporción (0,10 = 10 %) si es porcentaje

    @classmethod
    def desde_dict(cls, datos: dict) -> "Cargo":
        """Convierte un cargo guardado en ParametroMensual.cargos (JSON) en un Cargo validado."""
        tipo = datos.get("tipo")
        if tipo not in TIPOS_CARGO:
            raise ValueError(f"Tipo de cargo desconocido: {tipo!r}. Opciones: {sorted(TIPOS_CARGO)}")
        valor = Decimal(str(datos.get("valor", "0")))
        if valor < 0:
            raise ValueError("Un cargo no puede ser negativo.")
        return cls(concepto=str(datos.get("concepto", tipo)), tipo=tipo, valor=valor)


@dataclass(frozen=True)
class CuotaConCargos:
    numero: int
    vencimiento: date
    capital: int
    interes: int
    cargos: int        # suma de los cargos mensuales de esta cuota (G.)
    total: int         # capital + interés + cargos: lo que paga el cliente ese mes


@dataclass(frozen=True)
class Simulacion:
    """Todo lo que el cliente y el analista necesitan saber de un crédito, calculado en un solo lugar."""
    monto: int
    plazo_meses: int
    tasa_nominal_anual: Decimal
    cuotas: list[CuotaConCargos]
    cargos_iniciales: int          # se descuentan al desembolsar
    monto_liquido: int             # lo que el cliente recibe en mano
    total_cuotas: int              # suma de todas las cuotas
    costo_total: int               # total de cuotas + cargos iniciales (todo lo que paga el cliente)
    costo_financiero: int          # costo_total − monto (lo que cuesta el crédito además del capital)
    tasa_efectiva_anual: Decimal   # incluye intereses y TODOS los cargos
    cuota_mayor: int               # la cuota más alta (para compararla con la cuota máxima)
    tasa_maxima_anual: Decimal | None
    cumple_tasa_maxima_nominal: bool | None    # tasa nominal ≤ tasa máxima
    cumple_tasa_maxima_efectiva: bool | None   # tasa efectiva con cargos ≤ tasa máxima
    cumple_regla_apple: bool
    cuota_maxima: int | None       # según el ingreso y el % del mes (None si no se informó ingreso)
    entra_en_capacidad_de_pago: bool | None


def cuota_maxima(ingreso_mensual: int, pct_max_cuota_ingreso: Decimal) -> int:
    """
    Cuota más alta que se puede aprobar: ingreso × porcentaje del mes, redondeada HACIA ABAJO
    (redondear hacia arriba aprobaría un guaraní por encima del límite).
    Préstamo responsable: es la verificación de capacidad de pago.
    """
    if ingreso_mensual < 0:
        raise ValueError("El ingreso no puede ser negativo.")
    pct = Decimal(pct_max_cuota_ingreso)
    if not (0 <= pct <= 1):
        raise ValueError("El porcentaje tiene que estar entre 0 y 1 (por ejemplo 0,30).")
    return int(Decimal(ingreso_mensual) * pct)   # int() corta los decimales = redondeo hacia abajo


def aplicar_cargos(cuotas: list[CuotaCalculada], cargos: list[Cargo]) -> list[CuotaConCargos]:
    """Suma a cada cuota sus cargos mensuales (fijos, % del interés, % del saldo)."""
    resultado = []
    saldo_antes = sum(c.capital for c in cuotas)   # saldo de capital antes de la primera cuota = monto
    for c in cuotas:
        cargos_mes = Decimal(0)
        for cargo in cargos:
            if cargo.tipo == "mensual_fijo":
                cargos_mes += cargo.valor
            elif cargo.tipo == "pct_interes":
                cargos_mes += Decimal(c.interes) * cargo.valor
            elif cargo.tipo == "pct_saldo":
                cargos_mes += Decimal(saldo_antes) * cargo.valor
            # Los cargos "inicial_*" no van en las cuotas.
        cargos_redondeados = _redondear_guaranies(cargos_mes)
        resultado.append(CuotaConCargos(
            numero=c.numero, vencimiento=c.vencimiento, capital=c.capital, interes=c.interes,
            cargos=cargos_redondeados, total=c.capital + c.interes + cargos_redondeados,
        ))
        saldo_antes = c.saldo_despues
    return resultado


def cargos_iniciales(monto: int, cargos: list[Cargo]) -> int:
    """Suma de los cargos que se cobran al desembolsar."""
    total = Decimal(0)
    for cargo in cargos:
        if cargo.tipo == "inicial_fijo":
            total += cargo.valor
        elif cargo.tipo == "inicial_pct":
            total += Decimal(monto) * cargo.valor
    return _redondear_guaranies(total)


def tasa_efectiva_anual(monto_liquido: int, pagos_mensuales: list[int]) -> Decimal:
    """
    Tasa efectiva anual (TEA) que realmente paga el cliente, con TODOS los cargos.

    Idea: buscamos la tasa mensual i que hace que lo que el cliente recibe hoy sea igual a lo que
    paga después, "trayendo" cada pago al presente:
        monto_liquido = Σ pago_k / (1 + i)^k
    No hay fórmula directa: se busca por bisección (como adivinar un número diciendo "más alto" o
    "más bajo" y partiendo el rango a la mitad cada vez). Después: TEA = (1 + i)^12 − 1.

    Se usa float acá porque es una tasa, no dinero; el resultado se redondea a 6 decimales.
    """
    if monto_liquido <= 0:
        raise ValueError("El monto líquido tiene que ser mayor que cero.")

    def valor_presente(i: float) -> float:
        return sum(p / (1 + i) ** k for k, p in enumerate(pagos_mensuales, start=1))

    # Si paga lo mismo o menos de lo que recibió, no hay costo: la tasa es 0.
    if valor_presente(0.0) <= monto_liquido:
        return Decimal("0")
    bajo, alto = 0.0, 1.0            # entre 0 % y 100 % mensual
    for _ in range(100):             # 100 mitades: precisión mucho mayor que un guaraní
        medio = (bajo + alto) / 2
        if valor_presente(medio) > monto_liquido:
            bajo = medio             # la tasa es más alta
        else:
            alto = medio             # la tasa es más baja
    i = (bajo + alto) / 2
    return Decimal(str((1 + i) ** 12 - 1)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def simular(
    monto: int,
    plazo_meses: int,
    tasa_nominal_anual: Decimal,
    fecha_desembolso: date,
    cargos: list[Cargo] | None = None,
    tasa_maxima_anual: Decimal | None = None,
    ingreso_mensual: int | None = None,
    pct_max_cuota_ingreso: Decimal | None = None,
) -> Simulacion:
    """
    Calcula todo de una vez. Es la ÚNICA función que el panel, los canales y la app usan para
    mostrar condiciones de un crédito.

    Sobre la tasa máxima: NO SABEMOS si la ley compara el tope con la tasa nominal o con la tasa
    que incluye cargos. Por eso se devuelven las dos comparaciones (pregunta abierta para un abogado).
    """
    cargos = cargos or []
    tasa_nominal = Decimal(tasa_nominal_anual)
    cuotas = aplicar_cargos(
        cronograma(monto, tasa_mensual_desde_nominal_anual(tasa_nominal), plazo_meses, fecha_desembolso), cargos
    )
    iniciales = cargos_iniciales(monto, cargos)
    liquido = monto - iniciales
    if liquido <= 0:
        raise ValueError("Los cargos iniciales no pueden ser iguales o mayores que el monto.")
    total_cuotas = sum(c.total for c in cuotas)
    tea = tasa_efectiva_anual(liquido, [c.total for c in cuotas])

    if tasa_maxima_anual is not None:
        tope = Decimal(tasa_maxima_anual)
        cumple_nominal, cumple_efectiva = tasa_nominal <= tope, tea <= tope
    else:
        cumple_nominal = cumple_efectiva = None

    dias_hasta_el_final = (cuotas[-1].vencimiento - fecha_desembolso).days
    cumple_apple = tea <= APPLE_TASA_MAXIMA and dias_hasta_el_final > APPLE_PLAZO_MINIMO_DIAS

    cuota_mayor = max(c.total for c in cuotas)
    if ingreso_mensual is not None and pct_max_cuota_ingreso is not None:
        maxima = cuota_maxima(ingreso_mensual, pct_max_cuota_ingreso)
        entra = cuota_mayor <= maxima
    else:
        maxima, entra = None, None

    return Simulacion(
        monto=monto, plazo_meses=plazo_meses, tasa_nominal_anual=tasa_nominal, cuotas=cuotas,
        cargos_iniciales=iniciales, monto_liquido=liquido, total_cuotas=total_cuotas,
        costo_total=total_cuotas + iniciales, costo_financiero=total_cuotas + iniciales - monto,
        tasa_efectiva_anual=tea, cuota_mayor=cuota_mayor,
        tasa_maxima_anual=Decimal(tasa_maxima_anual) if tasa_maxima_anual is not None else None,
        cumple_tasa_maxima_nominal=cumple_nominal, cumple_tasa_maxima_efectiva=cumple_efectiva,
        cumple_regla_apple=cumple_apple, cuota_maxima=maxima, entra_en_capacidad_de_pago=entra,
    )
