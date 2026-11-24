# Datos sintéticos (Fase 1)

## Analogía

Un simulacro de incendio con actores. Los clientes, cédulas, empresas y pagos son inventados
siguiendo un guion (`datos_sinteticos/supuestos.py`). Como el guion lo escribimos nosotros, cada imagen
viene con su hoja de respuestas (`verdad.json`) para medir el OCR en la Fase 2.

**Límite:** un modelo entrenado con estos datos aprende el guion, no a los clientes reales.

## Cómo se usa

```bash
source venv/bin/activate
python -m datos_sinteticos.generar                      # 3.000 clientes, semilla 42, 40 con imágenes
python -m datos_sinteticos.generar --clientes 25000     # tamaño real declarado por Credisolución
python -m datos_sinteticos.generar --sesgo-edad         # siembra un sesgo por edad (Fase 5)
pytest                                                  # todos los tests
```

La salida va a `datos_generados/`, que no se sube a git. El generador solo borra esa carpeta si la creó él.

## Qué es real y qué es inventado

| Dato | Origen |
|---|---|
| Salario mínimo G. 3.044.000 | **Fuente:** Decreto 6225/2026, vigente desde el 1/7/2026 |
| Montos más pedidos (3, 5 y 10 millones) | **Fuente:** Credisolución |
| Nombres de los segmentos | **Fuente:** Credisolución |
| Aporte obrero IPS 9 % | Dato conocido, **a verificar** en la norma |
| CI de 8 dígitos que empiezan con 9 | **Inferencia:** las cédulas actuales no llegan a 8 dígitos |
| Prefijo de teléfono 0900 | **Inferencia:** no es un prefijo de celular en Paraguay |
| Tasa 28 % nominal anual, plazos, reparto por segmento, sucursal y canal | **SUPUESTO** |
| Probabilidades de mora, nivel de mora (6–25 % a más de 30 días) | **SUPUESTO**: no se encontró la morosidad publicada de Credisolución |
| Empresas e instituciones empleadoras | **Inventadas** |
| Diseño de cédula, liquidación y extracto IPS | **Inventado** (no imita los documentos oficiales) |

## Modelo de mora

1. **Riesgo mensual de cada cliente** = probabilidad de no pagar un mes estando al día:
   - parte del riesgo base del segmento;
   - × (1 + 3 × cuota/ingreso): más carga financiera, más riesgo;
   - × 1,5 si la antigüedad laboral es menor a 12 meses;
   - × un factor personal al azar (log-normal con media 1);
   - × las anomalías sembradas: cosechas 2025-12 (×2,5) y 2026-01 (×2,0), y sucursal Ciudad del Este (×1,6).
     Son grandes a propósito: con unos 120 créditos por cosecha, un efecto chico se pierde en el azar;
   - × 1,8 para menores de 25 años, **solo** con `--sesgo-edad`;
   - el sexo **no** interviene.
2. **Cada vencimiento** (una cadena de Markov: el próximo paso depende solo de cuántas cuotas se deben):
   - al día → paga (82 % en fecha, el resto con 1 a 25 días de atraso) o deja de pagar;
   - debe k cuotas → se pone al día, paga la más vieja o no paga nada. Cuanto mayor es k, más difícil volver.
3. **Con 6 cuotas adeudadas** (unos 180 días), el crédito se castiga.
4. **Se registran todos los pagos**, también los puntuales (idea del Cadastro Positivo).

El riesgo simulado **no se exporta**: es la respuesta del guion, y el score de la Fase 5 no debe verla.

## Salida

| Archivo | Contenido |
|---|---|
| `clientes.csv` | Datos personales ficticios, segmento, ingreso, empleador |
| `creditos.csv` | Condiciones, cosecha, canal, estado y días de atraso al corte (31/10/2026) |
| `cuotas.csv` | Cronograma del sistema francés (calculado con `backend/creditos/reglas.py`) y estado |
| `pagos.csv` | Cada pago con fecha, medio y días de atraso |
| `documentos/` | Imágenes JPG: cédula (frente y dorso) y, según el segmento, liquidación y extracto IPS |
| `verdad.json` | Valores correctos de cada imagen y su calidad (buena, borrosa, girada, oscura, faltante) |

## Simplificaciones

- Un crédito por cliente: sin renovaciones, refinanciaciones ni cancelaciones anticipadas.
- Las cuotas no incluyen cargos (IVA, seguros, gastos); llegan en la Fase 2 con `ParametroMensual`.
- El resumen muestra dos medidas por cosecha:
  - **Mora > 30 hoy:** sobre los créditos no cancelados. Las cosechas viejas se ven peor porque sus
    buenos pagadores ya cancelaron, así que no sirve para comparar cosechas.
  - **Mora temprana:** alguna de las primeras 6 cuotas con más de 30 días de atraso. Mide todas las cosechas
    a la misma "edad", que es la forma correcta de compararlas. Es la que va a usar el dashboard de la Fase 4.
    Las cosechas con menos de 6 cuotas vencidas no tienen todavía este dato.
- Los informales, independientes, contribuyentes de IVA, pymes y agro solo presentan cédula. Qué otros
  documentos pide Credisolución a esos segmentos está por confirmar.
