"""
Todas las cifras del generador de datos sintéticos, en UN solo archivo.

Regla del proyecto: no inventar parámetros escondidos en el código. Por eso cada número tiene su
etiqueta:
  - FUENTE: dato real, con su origen.
  - SUPUESTO: inventado para la simulación. Es razonable, pero NO es un dato de Credisolución.
    Si la empresa da el valor real, se reemplaza acá y todo el generador se ajusta solo.

Analogía: es el guion del simulacro. Los actores (clientes) hacen lo que este guion dice.
"""

from datetime import date
from decimal import Decimal

# ---------------------------------------------------------------------------
# Generales
# ---------------------------------------------------------------------------

# Semilla por defecto: con la misma semilla se generan exactamente los mismos datos.
SEMILLA_POR_DEFECTO = 42

# Cantidad de clientes por defecto. Credisolución declara más de 25.000; 3.000 alcanza para la demo.
CLIENTES_POR_DEFECTO = 3_000

# Cantidad de clientes a los que se les dibujan imágenes de documentos.
# Dibujar las de los 3.000 ocuparía cientos de MB; para probar el OCR y la demo alcanza con pocos.
CLIENTES_CON_IMAGENES_POR_DEFECTO = 40

# Fecha de corte: "hoy" dentro de la simulación. Los datos llegan hasta este día.
# SUPUESTO: elegida para que la historia termine poco antes de la fecha del proyecto (nov 2026).
FECHA_CORTE = date(2026, 10, 31)

# Meses de historia de desembolsos (cosechas). Pedido del proyecto: 24 meses.
MESES_HISTORIA = 24

# ---------------------------------------------------------------------------
# Cédulas y contacto ficticios
# ---------------------------------------------------------------------------

# Rango de CI ficticias: 8 dígitos que empiezan con 9.
# INFERENCIA (no verificada en fuente oficial): las cédulas paraguayas emitidas hasta hoy
# tienen como máximo 7 dígitos, así que este rango no coincide con personas reales.
CI_MINIMA = 90_000_000
CI_MAXIMA = 99_999_999

# Prefijo de teléfono ficticio. INFERENCIA: "0900" no es un prefijo de celular en Paraguay
# (los celulares usan 096x, 097x, 098x y 099x).
PREFIJO_TELEFONO_FICTICIO = "0900"

# Dominio de correo reservado por norma (RFC 2606): ".invalid" nunca existe en internet.
DOMINIO_CORREO_FICTICIO = "ejemplo.invalid"

# ---------------------------------------------------------------------------
# Ingresos
# ---------------------------------------------------------------------------

# FUENTE: Decreto N.º 6225/2026, salario mínimo para actividades diversas no especificadas,
# vigente desde el 1/7/2026 (antes: G. 2.899.048).
SALARIO_MINIMO = 3_044_000

# FUENTE A VERIFICAR: aporte obrero al IPS del 9 % del salario (dato conocido, no confirmado
# en la norma para este proyecto). Se usa solo para dibujar la liquidación sintética.
APORTE_IPS_OBRERO = Decimal("0.09")

# ---------------------------------------------------------------------------
# Segmentos de clientes
# ---------------------------------------------------------------------------
# Para cada segmento (todo SUPUESTO salvo los nombres, que vienen de Credisolución):
#   peso: qué proporción de clientes pertenece al segmento.
#   ingreso_sm: rango del ingreso mensual en cantidad de salarios mínimos (mín, máx).
#   riesgo_base: probabilidad mensual base de NO pagar la cuota del mes.
#   edad: rango de edad (mín, máx).
#   documentos: qué documentos presenta (cédula siempre; liquidación e IPS si corresponde).
SEGMENTOS = {
    "ips": {
        "nombre": "Asalariado con IPS",
        "peso": 0.34, "ingreso_sm": (1.0, 4.0), "riesgo_base": 0.030, "edad": (20, 62),
        "documentos": ["ci_frente", "ci_dorso", "liquidacion", "extracto_ips"],
    },
    "funcionario": {
        "nombre": "Funcionario público",
        "peso": 0.16, "ingreso_sm": (1.0, 4.5), "riesgo_base": 0.022, "edad": (22, 64),
        "documentos": ["ci_frente", "ci_dorso", "liquidacion"],
    },
    "jubilado": {
        "nombre": "Jubilado",
        "peso": 0.08, "ingreso_sm": (1.0, 3.0), "riesgo_base": 0.020, "edad": (60, 82),
        "documentos": ["ci_frente", "ci_dorso", "liquidacion"],
    },
    "informal": {
        "nombre": "Trabajador informal",
        "peso": 0.14, "ingreso_sm": (0.8, 2.5), "riesgo_base": 0.060, "edad": (19, 60),
        "documentos": ["ci_frente", "ci_dorso"],
    },
    "independiente": {
        "nombre": "Independiente",
        "peso": 0.10, "ingreso_sm": (1.0, 5.0), "riesgo_base": 0.045, "edad": (22, 64),
        "documentos": ["ci_frente", "ci_dorso"],
    },
    "iva": {
        "nombre": "Contribuyente de IVA",
        "peso": 0.10, "ingreso_sm": (1.5, 6.0), "riesgo_base": 0.035, "edad": (24, 64),
        "documentos": ["ci_frente", "ci_dorso"],
    },
    "pyme": {
        "nombre": "Pyme",
        "peso": 0.05, "ingreso_sm": (2.0, 8.0), "riesgo_base": 0.040, "edad": (25, 64),
        "documentos": ["ci_frente", "ci_dorso"],
    },
    "agro": {
        "nombre": "Agro",
        "peso": 0.03, "ingreso_sm": (1.5, 7.0), "riesgo_base": 0.050, "edad": (25, 66),
        "documentos": ["ci_frente", "ci_dorso"],
    },
}

# Segmentos con empleador y antigüedad laboral (los demás no tienen "empleador").
SEGMENTOS_CON_EMPLEADOR = {"ips", "funcionario"}

# ---------------------------------------------------------------------------
# Sucursales y canales (pesos SUPUESTOS; las ciudades son reales, las sucursales no)
# ---------------------------------------------------------------------------
SUCURSALES = {
    "Asunción Centro": 0.24,
    "San Lorenzo": 0.15,
    "Luque": 0.12,
    "Fernando de la Mora": 0.10,
    "Capiatá": 0.10,
    "Ciudad del Este": 0.12,
    "Encarnación": 0.09,
    "Coronel Oviedo": 0.08,
}

# Canal de origen al principio y al final de los 24 meses: el peso de cada canal se mueve en
# línea recta entre esos dos valores (SUPUESTO: lo digital crece con el tiempo).
CANALES_INICIO = {"sucursal": 0.45, "whatsapp": 0.30, "telefono": 0.15, "web": 0.10, "app": 0.00}
CANALES_FIN = {"sucursal": 0.30, "whatsapp": 0.35, "telefono": 0.10, "web": 0.15, "app": 0.10}

# ---------------------------------------------------------------------------
# Condiciones de los créditos (SUPUESTO)
# ---------------------------------------------------------------------------

# Montos pedidos y su peso. Los tres primeros son los más pedidos según Credisolución (FUENTE).
MONTOS = {3_000_000: 0.30, 5_000_000: 0.28, 10_000_000: 0.20, 2_000_000: 0.08,
          7_000_000: 0.09, 15_000_000: 0.05}

# Plazos en meses y su peso.
PLAZOS = {12: 0.30, 18: 0.25, 24: 0.30, 36: 0.15}

# SUPUESTO: tasa nominal anual de la simulación. NO es la tasa de Credisolución ni la tasa
# máxima del BCP; ambas se cargarán como parámetro mensual en la Fase 2.
TASA_NOMINAL_ANUAL = Decimal("0.28")

# SUPUESTO: relación cuota/ingreso máxima que se usó al aprobar los créditos históricos.
# Si la cuota supera este límite, el generador baja el monto o alarga el plazo (como haría
# un analista). La política real de Credisolución está por confirmar.
CUOTA_INGRESO_MAXIMA_HISTORICA = Decimal("0.30")

# ---------------------------------------------------------------------------
# Modelo de mora (SUPUESTO, ver docs/datos-sinteticos.md)
# ---------------------------------------------------------------------------

# Probabilidad de que un cliente al día pague en fecha o antes (el resto paga con unos días de atraso).
PROB_PAGO_PUNTUAL = 0.82

# Días de atraso de un pago "tarde pero dentro del mes".
ATRASO_LEVE_DIAS = (1, 25)

# Cuando el cliente debe k cuotas, probabilidad de ponerse al día de golpe ese mes.
# Cuanto más atrasado, más difícil volver. La clave es k (cuotas adeudadas).
PROB_PONERSE_AL_DIA = {1: 0.45, 2: 0.25, 3: 0.12, 4: 0.05, 5: 0.03}

# Cuando el cliente debe k cuotas y NO se pone al día, probabilidad de pagar al menos una
# (frena la caída pero no la revierte).
PROB_PAGAR_UNA = {1: 0.30, 2: 0.25, 3: 0.18, 4: 0.10, 5: 0.05}

# Cuotas adeudadas a partir de las cuales el crédito se considera castigado (≈180 días).
CUOTAS_PARA_CASTIGO = 6

# Efecto de la carga financiera: el riesgo se multiplica por (1 + este valor × cuota/ingreso).
EFECTO_CUOTA_INGRESO = 3.0

# Efecto de la antigüedad laboral (solo segmentos con empleador): menos de 12 meses, más riesgo.
MULTIPLICADOR_ANTIGUEDAD_BAJA = 1.5
ANTIGUEDAD_BAJA_MESES = 12

# Dispersión del riesgo individual: el riesgo de cada cliente se multiplica por un factor
# aleatorio log-normal con esta desviación (dos clientes del mismo segmento no son iguales).
DISPERSION_RIESGO = 0.6

# Tope del riesgo mensual (nadie tiene más de esta probabilidad de dejar de pagar un mes).
RIESGO_MAXIMO = 0.60

# Anomalías SEMBRADAS a propósito para que el dashboard de la Fase 4 tenga algo que detectar.
# Clave: cosecha "AAAA-MM" o sucursal; valor: multiplicador del riesgo.
# Los multiplicadores son grandes a propósito: con unos 120 créditos por cosecha, un efecto chico
# se pierde en el azar y el dashboard no tendría nada claro que mostrar.
COSECHAS_ANOMALAS = {"2025-12": 2.5, "2026-01": 2.0}
SUCURSALES_ANOMALAS = {"Ciudad del Este": 1.6}

# Opción --sesgo-edad (apagada por defecto): menores de esta edad tienen el riesgo multiplicado.
# Sirve para comprobar en la Fase 5 que el detector de sesgo lo encuentra.
SESGO_EDAD_LIMITE = 25
SESGO_EDAD_MULTIPLICADOR = 1.8

# Rango esperado de la mora mayor a 30 días al corte, sobre los créditos no cancelados.
# SUPUESTO: no se encontró la morosidad publicada de Credisolución (búsqueda del 23/11/2026).
# Los tests verifican que el generador quede dentro de este rango.
MORA_30_ESPERADA = (0.06, 0.25)

# ---------------------------------------------------------------------------
# Medios de pago (SUPUESTO)
# ---------------------------------------------------------------------------
MEDIOS_PAGO = {"sucursal": 0.40, "boca_cobranza": 0.30, "transferencia": 0.20, "app": 0.10}

# ---------------------------------------------------------------------------
# Imágenes de documentos (SUPUESTO)
# ---------------------------------------------------------------------------
# Probabilidad de que cada documento salga en cada estado. "faltante" = no se genera el archivo.
CALIDAD_DOCUMENTOS = {"buena": 0.80, "borrosa": 0.06, "girada": 0.05, "oscura": 0.05, "faltante": 0.04}

# Texto de la marca de agua de todas las imágenes.
MARCA_DE_AGUA = "MUESTRA - SIN VALOR"
