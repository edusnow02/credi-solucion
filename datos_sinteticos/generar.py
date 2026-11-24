"""
Orden principal del generador de datos sintéticos.

Uso (desde la raíz del proyecto, con el entorno virtual activado):
    python -m datos_sinteticos.generar
    python -m datos_sinteticos.generar --clientes 25000 --semilla 7 --con-imagenes 100
    python -m datos_sinteticos.generar --sesgo-edad      # siembra un sesgo por edad (para la Fase 5)

Escribe en datos_generados/ (no se sube a git):
    clientes.csv, creditos.csv, cuotas.csv, pagos.csv   → se cargan en la base en la Fase 2
    documentos/<cliente>/<tipo>.jpg                      → imágenes falsas para el OCR
    verdad.json                                          → hoja de respuestas de cada imagen
    LEEME.txt                                            → aviso de que todo es ficticio
"""

import argparse
import csv
import json
import random
import shutil
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

# El generador usa la calculadora del backend (creditos.reglas). Agregamos backend/ al camino de
# búsqueda de Python para poder importarla sin instalar nada.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from datos_sinteticos import supuestos  # noqa: E402  (va después de ajustar sys.path)
from datos_sinteticos.documentos import generar_documentos  # noqa: E402
from datos_sinteticos.historial import (  # noqa: E402
    dias_atraso_al_corte,
    generar_creditos,
    mora_temprana,
    tasa_mora_30,
)
from datos_sinteticos.personas import generar_personas  # noqa: E402

# Archivo "marca" que indica que una carpeta la creó este generador. Solo borramos carpetas que
# lo tengan: así nunca borramos por error una carpeta con otras cosas.
MARCA_CARPETA = ".generado_por_datos_sinteticos"


def _preparar_carpeta(carpeta: Path) -> None:
    """Deja la carpeta de salida vacía, pero solo si la creó este generador (o no existe)."""
    if carpeta.exists() and any(carpeta.iterdir()):
        if not (carpeta / MARCA_CARPETA).exists():
            sys.exit(f"La carpeta {carpeta} tiene archivos que no creó el generador. Elegí otra con --salida.")
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / MARCA_CARPETA).write_text("Carpeta creada por datos_sinteticos.generar\n", encoding="utf-8")


def _escribir_csv(ruta: Path, filas: list[dict]) -> None:
    """Escribe una lista de diccionarios como CSV (encabezado = claves del primero)."""
    if not filas:
        ruta.write_text("", encoding="utf-8")
        return
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


def generar(clientes: int, semilla: int, con_imagenes: int, sesgo_edad: bool, carpeta: Path) -> dict:
    """Genera todo y devuelve un resumen con las cifras principales."""
    # UN solo generador de azar con la semilla: mismos parámetros → mismos datos.
    rng = random.Random(semilla)

    personas = generar_personas(rng, clientes)
    creditos = generar_creditos(rng, personas, sesgo_edad=sesgo_edad)

    # Imágenes solo para una muestra de clientes (dibujarlas todas ocuparía cientos de MB).
    muestra = rng.sample(personas, min(con_imagenes, len(personas)))
    _preparar_carpeta(carpeta)
    documentos = generar_documentos(rng, muestra, carpeta)

    # --- Escritura de archivos -------------------------------------------------
    _escribir_csv(carpeta / "clientes.csv", [
        {
            "id": p.id, "ci": p.ci, "nombres": p.nombres, "apellidos": p.apellidos, "sexo": p.sexo,
            "fecha_nacimiento": p.fecha_nacimiento.isoformat(), "segmento": p.segmento,
            "sucursal": p.sucursal, "telefono": p.telefono, "correo": p.correo,
            "ingreso_mensual": p.ingreso_mensual, "empleador": p.empleador, "cargo": p.cargo,
            "fecha_ingreso_laboral": p.fecha_ingreso_laboral.isoformat() if p.fecha_ingreso_laboral else "",
        }
        for p in personas
    ])
    _escribir_csv(carpeta / "creditos.csv", [
        {
            "id": c.id, "cliente_id": c.cliente_id, "monto": c.monto, "plazo_meses": c.plazo_meses,
            "tasa_nominal_anual": str(c.tasa_nominal_anual), "cuota": c.cuota,
            "fecha_desembolso": c.fecha_desembolso.isoformat(), "cosecha": c.cosecha,
            "sucursal": c.sucursal, "segmento": c.segmento, "canal": c.canal,
            "cuota_ingreso": str(c.cuota_ingreso), "estado": c.estado,
            "dias_atraso_al_corte": dias_atraso_al_corte(c),
            # riesgo_mensual NO se exporta a propósito (es la "respuesta" del simulacro).
        }
        for c in creditos
    ])
    _escribir_csv(carpeta / "cuotas.csv", [
        {
            "credito_id": q.credito_id, "numero": q.numero, "vencimiento": q.vencimiento.isoformat(),
            "capital": q.capital, "interes": q.interes, "total": q.total, "estado": q.estado,
            "fecha_pago": q.fecha_pago.isoformat() if q.fecha_pago else "", "dias_atraso": q.dias_atraso,
        }
        for c in creditos for q in c.cuotas
    ])
    _escribir_csv(carpeta / "pagos.csv", [
        {
            "id": pg.id, "credito_id": pg.credito_id, "cuota_numero": pg.cuota_numero,
            "fecha": pg.fecha.isoformat(), "monto": pg.monto, "medio": pg.medio, "dias_atraso": pg.dias_atraso,
        }
        for c in creditos for pg in c.pagos
    ])
    (carpeta / "verdad.json").write_text(
        json.dumps([asdict(d) for d in documentos], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (carpeta / "LEEME.txt").write_text(
        "DATOS SINTÉTICOS. Todas las personas, cédulas, empresas, créditos y pagos de esta carpeta\n"
        "son ficticios y fueron generados por datos_sinteticos.generar.\n"
        f"Semilla: {semilla}. Clientes: {clientes}. Sesgo por edad sembrado: {'sí' if sesgo_edad else 'no'}.\n",
        encoding="utf-8",
    )
    # Datos para el backend: la fecha de corte le permite a cargar_sinteticos mover las fechas a "hoy".
    (carpeta / "meta.json").write_text(
        json.dumps({"fecha_corte": supuestos.FECHA_CORTE.isoformat(), "semilla": semilla,
                    "clientes": clientes, "sesgo_edad": sesgo_edad}, indent=2),
        encoding="utf-8",
    )

    # --- Resumen ---------------------------------------------------------------
    por_cosecha = defaultdict(list)
    for c in creditos:
        por_cosecha[c.cosecha].append(c)
    return {
        "clientes": len(personas),
        "creditos": len(creditos),
        "cuotas": sum(len(c.cuotas) for c in creditos),
        "pagos": sum(len(c.pagos) for c in creditos),
        "pagos_puntuales": sum(1 for c in creditos for p in c.pagos if p.dias_atraso == 0),
        "estados": {e: sum(1 for c in creditos if c.estado == e) for e in ("vigente", "en_mora", "cancelado", "castigado")},
        "mora_30": tasa_mora_30(creditos),
        "mora_temprana": mora_temprana(creditos),
        # Por cosecha: (cantidad, mora > 30 hoy, mora temprana o None si la cosecha es muy nueva).
        "por_cosecha": {
            k: (len(v), tasa_mora_30(v), mora_temprana(v) if _madura(v) else None)
            for k, v in sorted(por_cosecha.items())
        },
        "imagenes": sum(1 for d in documentos if d.archivo),
        "documentos_faltantes": sum(1 for d in documentos if d.calidad == "faltante"),
    }


def _madura(creditos) -> bool:
    """¿Algún crédito de la cosecha ya tuvo 6 cuotas vencidas? (si no, la mora temprana no existe aún)."""
    return any(len(c.cuotas) >= 6 and c.cuotas[5].vencimiento <= supuestos.FECHA_CORTE for c in creditos)


def _imprimir_resumen(r: dict, carpeta: Path) -> None:
    """Muestra el resumen en la terminal en un formato fácil de leer."""
    print(f"\nDatos sintéticos generados en {carpeta}\n")
    print(f"  Clientes:  {r['clientes']:>7,}".replace(",", "."))
    print(f"  Créditos:  {r['creditos']:>7,}".replace(",", "."))
    print(f"  Cuotas:    {r['cuotas']:>7,}".replace(",", "."))
    print(f"  Pagos:     {r['pagos']:>7,}  ({r['pagos_puntuales'] / max(r['pagos'], 1):.0%} en fecha)".replace(",", "."))
    print("  Estados:   " + ", ".join(f"{k} {v}" for k, v in r["estados"].items()))
    print(f"  Mora > 30 días hoy (créditos no cancelados): {r['mora_30']:.1%}")
    print(f"  Mora temprana (> 30 días en alguna de las 6 primeras cuotas): {r['mora_temprana']:.1%}")
    print(f"  Imágenes:  {r['imagenes']} (faltantes a propósito: {r['documentos_faltantes']})\n")
    print("  Cosecha   Créditos  Mora>30 hoy  Mora temprana")
    for cosecha, (cantidad, mora, temprana) in r["por_cosecha"].items():
        texto_temprana = f"{temprana:>8.1%}" if temprana is not None else "   (nueva)"
        print(f"  {cosecha}   {cantidad:>6}   {mora:>8.1%}    {texto_temprana}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera datos sintéticos paraguayos para la demo de Credisolución.")
    parser.add_argument("--clientes", type=int, default=supuestos.CLIENTES_POR_DEFECTO, help="cantidad de clientes")
    parser.add_argument("--semilla", type=int, default=supuestos.SEMILLA_POR_DEFECTO, help="semilla del azar")
    parser.add_argument("--con-imagenes", type=int, default=supuestos.CLIENTES_CON_IMAGENES_POR_DEFECTO,
                        help="a cuántos clientes se les dibujan documentos")
    parser.add_argument("--sesgo-edad", action="store_true", help="siembra un sesgo por edad (para probar la Fase 5)")
    parser.add_argument("--salida", type=Path, default=RAIZ / "datos_generados", help="carpeta de salida")
    args = parser.parse_args()

    if args.clientes <= 0:
        sys.exit("--clientes tiene que ser mayor que cero.")
    resumen = generar(args.clientes, args.semilla, args.con_imagenes, args.sesgo_edad, args.salida)
    _imprimir_resumen(resumen, args.salida)


if __name__ == "__main__":
    main()
