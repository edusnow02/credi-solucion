"""
Tests del generador de datos sintéticos.

Comprueban que los datos sean ficticios, coherentes y reproducibles, y que la mora quede
dentro del rango definido en supuestos.py.
"""

import json
import random
from collections import Counter

import pytest
from PIL import Image

from datos_sinteticos import supuestos
from datos_sinteticos.generar import MARCA_CARPETA, generar
from datos_sinteticos.historial import generar_creditos, mora_temprana, tasa_mora_30
from datos_sinteticos.personas import formatear_ci, generar_personas

# Tamaño para los tests: suficiente para que las proporciones sean estables y rápido de correr.
N = 3000


@pytest.fixture(scope="module")
def datos():
    """Genera personas y créditos una sola vez para todos los tests de este archivo."""
    rng = random.Random(supuestos.SEMILLA_POR_DEFECTO)
    personas = generar_personas(rng, N)
    creditos = generar_creditos(rng, personas)
    return personas, creditos


# --- Personas -------------------------------------------------------------------

def test_ci_unicas_y_en_rango_ficticio(datos):
    personas, _ = datos
    cis = [p.ci for p in personas]
    assert len(set(cis)) == len(cis)
    assert all(supuestos.CI_MINIMA <= ci <= supuestos.CI_MAXIMA for ci in cis)


def test_contactos_ficticios(datos):
    personas, _ = datos
    assert all(p.telefono.startswith(supuestos.PREFIJO_TELEFONO_FICTICIO) for p in personas)
    assert all(p.correo.endswith("@" + supuestos.DOMINIO_CORREO_FICTICIO) for p in personas)


def test_formato_ci_paraguayo():
    assert formatear_ci(91234567) == "91.234.567"


def test_edades_dentro_del_rango_del_segmento(datos):
    personas, _ = datos
    for p in personas:
        edad_min, edad_max = supuestos.SEGMENTOS[p.segmento]["edad"]
        assert edad_min <= p.edad_en(supuestos.FECHA_CORTE) <= edad_max


def test_solo_asalariados_y_funcionarios_tienen_antiguedad(datos):
    personas, _ = datos
    for p in personas:
        tiene = p.fecha_ingreso_laboral is not None
        assert tiene == (p.segmento in supuestos.SEGMENTOS_CON_EMPLEADOR)


# --- Créditos, cuotas y pagos -------------------------------------------------

def test_guaranies_enteros(datos):
    _, creditos = datos
    for c in creditos:
        assert isinstance(c.monto, int) and isinstance(c.cuota, int)
        assert all(isinstance(q.total, int) for q in c.cuotas)
        assert all(isinstance(p.monto, int) for p in c.pagos)


def test_cuota_respeta_el_limite_historico_de_cuota_ingreso(datos):
    personas, creditos = datos
    ingreso = {p.id: p.ingreso_mensual for p in personas}
    for c in creditos:
        assert c.cuota <= ingreso[c.cliente_id] * float(supuestos.CUOTA_INGRESO_MAXIMA_HISTORICA) + 1


def test_desembolsos_dentro_de_los_24_meses(datos):
    _, creditos = datos
    cosechas = {c.cosecha for c in creditos}
    assert len(cosechas) == supuestos.MESES_HISTORIA
    assert all(c.fecha_desembolso <= supuestos.FECHA_CORTE for c in creditos)


def test_ningun_pago_despues_del_corte_ni_antes_del_desembolso(datos):
    _, creditos = datos
    for c in creditos:
        for p in c.pagos:
            assert c.fecha_desembolso <= p.fecha <= supuestos.FECHA_CORTE


def test_cada_cuota_pagada_tiene_exactamente_un_pago(datos):
    _, creditos = datos
    for c in creditos:
        pagos_por_cuota = Counter(p.cuota_numero for p in c.pagos)
        for q in c.cuotas:
            assert pagos_por_cuota[q.numero] == (1 if q.estado == "pagada" else 0)


def test_estados_coherentes_con_las_cuotas(datos):
    _, creditos = datos
    for c in creditos:
        if c.estado == "cancelado":
            assert all(q.estado == "pagada" for q in c.cuotas)
        if c.estado == "vigente":
            assert not any(q.estado == "atrasada" for q in c.cuotas)
        # Ninguna cuota futura (después del corte) puede estar atrasada.
        assert all(q.estado != "atrasada" for q in c.cuotas if q.vencimiento > supuestos.FECHA_CORTE)


def test_se_registran_tambien_los_pagos_al_dia(datos):
    # Idea del Cadastro Positivo: la mayoría de los pagos son puntuales y quedan registrados.
    _, creditos = datos
    pagos = [p for c in creditos for p in c.pagos]
    puntuales = sum(1 for p in pagos if p.dias_atraso == 0)
    assert puntuales / len(pagos) > 0.5


def test_mora_30_dentro_del_rango_esperado(datos):
    _, creditos = datos
    minimo, maximo = supuestos.MORA_30_ESPERADA
    assert minimo <= tasa_mora_30(creditos) <= maximo


def test_cosechas_anomalas_se_notan_en_la_mora_temprana(datos):
    # Las cosechas sembradas (2025-12 y 2026-01) tienen que tener claramente más mora temprana
    # que las cosechas vecinas (2025-10, 2025-11, 2026-02, 2026-03): al menos 10 puntos más.
    _, creditos = datos
    anomalas = [c for c in creditos if c.cosecha in supuestos.COSECHAS_ANOMALAS]
    vecinas = [c for c in creditos if c.cosecha in {"2025-10", "2025-11", "2026-02", "2026-03"}]
    assert mora_temprana(anomalas) > mora_temprana(vecinas) + 0.10


def test_sucursal_anomala_se_nota_en_la_mora_temprana(datos):
    _, creditos = datos
    anomala = [c for c in creditos if c.sucursal in supuestos.SUCURSALES_ANOMALAS]
    resto = [c for c in creditos if c.sucursal not in supuestos.SUCURSALES_ANOMALAS]
    assert mora_temprana(anomala) > mora_temprana(resto) + 0.05


def test_sin_sesgo_la_mora_no_difiere_por_sexo(datos):
    # El sexo no entra al riesgo: la diferencia entre F y M tiene que ser solo azar (< 4 puntos).
    personas, creditos = datos
    sexo = {p.id: p.sexo for p in personas}
    mujeres = [c for c in creditos if sexo[c.cliente_id] == "F"]
    varones = [c for c in creditos if sexo[c.cliente_id] == "M"]
    assert abs(tasa_mora_30(mujeres) - tasa_mora_30(varones)) < 0.04
    assert abs(mora_temprana(mujeres) - mora_temprana(varones)) < 0.04


def test_con_sesgo_de_edad_los_jovenes_tienen_mas_mora():
    # Con --sesgo-edad, los menores de 25 tienen que mostrar más mora temprana que el resto.
    rng = random.Random(supuestos.SEMILLA_POR_DEFECTO)
    personas = generar_personas(rng, N)
    creditos = generar_creditos(rng, personas, sesgo_edad=True)
    por_id = {p.id: p for p in personas}
    def es_joven(c):
        return por_id[c.cliente_id].edad_en(c.fecha_desembolso) < supuestos.SESGO_EDAD_LIMITE
    jovenes = [c for c in creditos if es_joven(c)]
    resto = [c for c in creditos if not es_joven(c)]
    assert mora_temprana(jovenes) > mora_temprana(resto) + 0.08


def test_riesgo_no_se_exporta(tmp_path):
    # El riesgo simulado es la "respuesta del guion": no puede aparecer en los CSV.
    generar(50, 1, 0, False, tmp_path / "salida")
    encabezado = (tmp_path / "salida" / "creditos.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "riesgo" not in encabezado


# --- Reproducibilidad ----------------------------------------------------------

def test_misma_semilla_mismos_datos(tmp_path):
    generar(200, 7, 3, False, tmp_path / "a")
    generar(200, 7, 3, False, tmp_path / "b")
    for nombre in ["clientes.csv", "creditos.csv", "cuotas.csv", "pagos.csv", "verdad.json"]:
        assert (tmp_path / "a" / nombre).read_bytes() == (tmp_path / "b" / nombre).read_bytes()


def test_otra_semilla_otros_datos(tmp_path):
    generar(200, 7, 0, False, tmp_path / "a")
    generar(200, 8, 0, False, tmp_path / "b")
    assert (tmp_path / "a" / "clientes.csv").read_bytes() != (tmp_path / "b" / "clientes.csv").read_bytes()


# --- Imágenes y hoja de respuestas --------------------------------------------

def test_imagenes_con_su_verdad(tmp_path):
    salida = tmp_path / "salida"
    resumen = generar(300, 3, 30, False, salida)
    verdad = json.loads((salida / "verdad.json").read_text(encoding="utf-8"))
    assert resumen["imagenes"] > 0
    for doc in verdad:
        # Cada documento tiene campos de verdad con la CI.
        assert doc["campos"]["ci"].isdigit()
        if doc["calidad"] == "faltante":
            assert doc["archivo"] is None
        else:
            ruta = salida / doc["archivo"]
            assert ruta.exists()
            with Image.open(ruta) as imagen:
                assert imagen.width > 500 and imagen.height > 500


def test_liquidacion_trae_salario_y_antiguedad(tmp_path):
    salida = tmp_path / "salida"
    generar(300, 3, 60, False, salida)
    verdad = json.loads((salida / "verdad.json").read_text(encoding="utf-8"))
    liquidaciones = [d for d in verdad if d["tipo"] == "liquidacion"]
    assert liquidaciones, "con 60 clientes debería haber al menos una liquidación"
    for d in liquidaciones:
        assert d["campos"]["salario"] > 0
        assert d["campos"]["empleador"]


def test_no_borra_carpetas_ajenas(tmp_path):
    # Si la carpeta de salida tiene archivos que no creó el generador, se niega a borrarla.
    ajena = tmp_path / "ajena"
    ajena.mkdir()
    (ajena / "importante.txt").write_text("no borrar")
    with pytest.raises(SystemExit):
        generar(10, 1, 0, False, ajena)
    assert (ajena / "importante.txt").exists()


def test_regenerar_en_la_misma_carpeta(tmp_path):
    salida = tmp_path / "salida"
    generar(10, 1, 0, False, salida)
    assert (salida / MARCA_CARPETA).exists()
    generar(10, 2, 0, False, salida)   # no tiene que fallar: la carpeta es del generador
