"""
Configuración del onboarding que NO cambia entre entornos (lo que sí cambia está en settings.ONBOARDING).

Todo acá está escrito para los documentos SINTÉTICOS de la Fase 1. Con documentos reales
(cédula, liquidaciones e IPS verdaderos) hay que revisar etiquetas y campos.
"""

# Documentos que se le piden a cada segmento. SUPUESTO: Credisolución tiene que confirmar qué pide
# realmente (por ejemplo, a informales o pymes seguramente les pide otros comprobantes de ingreso).
DOCUMENTOS_REQUERIDOS = {
    "ips": ["ci_frente", "ci_dorso", "liquidacion", "extracto_ips"],
    "funcionario": ["ci_frente", "ci_dorso", "liquidacion"],
    "jubilado": ["ci_frente", "ci_dorso", "liquidacion"],
    "informal": ["ci_frente", "ci_dorso"],
    "independiente": ["ci_frente", "ci_dorso"],
    "iva": ["ci_frente", "ci_dorso"],
    "pyme": ["ci_frente", "ci_dorso"],
    "agro": ["ci_frente", "ci_dorso"],
}

# Campos que se extraen de cada tipo de documento, con la etiqueta que los precede en la imagen.
# "etiqueta": texto del rótulo (se compara sin tildes ni mayúsculas, con tolerancia a errores del OCR).
CAMPOS_POR_TIPO = {
    "ci_frente": {
        "apellidos": {"etiqueta": "APELLIDOS", "tipo": "nombre"},
        "nombres": {"etiqueta": "NOMBRES", "tipo": "nombre"},
        "ci": {"etiqueta": "DE DOCUMENTO", "tipo": "ci"},
        "fecha_nacimiento": {"etiqueta": "FECHA DE NACIMIENTO", "tipo": "fecha"},
        "sexo": {"etiqueta": "SEXO", "tipo": "sexo"},
    },
    "ci_dorso": {
        "ci": {"etiqueta": "DE DOCUMENTO", "tipo": "ci"},
        "vencimiento": {"etiqueta": "FECHA DE VENCIMIENTO", "tipo": "fecha"},
    },
    "liquidacion": {
        "empleador": {"etiqueta": "EMPLEADOR", "tipo": "texto"},
        "nombre": {"etiqueta": "TRABAJADOR", "tipo": "nombre"},
        "ci": {"etiqueta": "C.I. N", "tipo": "ci"},
        "fecha_ingreso": {"etiqueta": "FECHA DE INGRESO", "tipo": "fecha"},
        "salario": {"etiqueta": "SALARIO BASICO", "tipo": "monto"},
    },
    "extracto_ips": {
        "nombre": {"etiqueta": "ASEGURADO", "tipo": "nombre"},
        "ci": {"etiqueta": "C.I. N", "tipo": "ci"},
        "empleador": {"etiqueta": "EMPLEADOR", "tipo": "texto"},
        "antiguedad_meses": {"etiqueta": "MESES DE APORTE CON ESTE EMPLEADOR", "tipo": "entero"},
        "salario": {"etiqueta": "SALARIO IMPONIBLE", "tipo": "monto"},
    },
    # La selfie no se lee con OCR: pasa por el puerto de verificación facial (simulado).
    "selfie": {},
}

# Ángulos (en grados) que se prueban para enderezar una foto torcida cuando la primera lectura
# sale con poca confianza. Cada intento es una lectura más de Tesseract (≈ 0,5 s cada una).
ANGULOS_ENDEREZADO = [-10, -6, -3, 3, 6, 10]

# Confianza promedio por debajo de la cual vale la pena probar enderezar la imagen.
CONFIANZA_PARA_REINTENTAR = 0.80

# Límites de los archivos que se aceptan.
TAMANIO_MAXIMO_BYTES = 10 * 1024 * 1024          # 10 MB
FORMATOS_ACEPTADOS = {"JPEG": "image/jpeg", "PNG": "image/png"}
