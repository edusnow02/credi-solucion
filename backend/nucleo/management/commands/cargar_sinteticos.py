"""
Carga en la base los datos sintéticos de la Fase 1 (datos_generados/).

Uso:
    python manage.py cargar_sinteticos                  # mueve las fechas para que el corte sea hoy
    python manage.py cargar_sinteticos --sin-desplazar  # deja las fechas como las generó la Fase 1

Por qué mover las fechas: los datos se generaron con un "hoy" fijo (fecha de corte). Si se cargan
semanas después, las cuotas que vencieron en el medio aparecerían impagas sin motivo. Corriendo
todas las fechas la misma cantidad de días, la historia queda igual pero termina hoy.

Además, si no hay parámetros para el mes actual, crea unos marcados SUPUESTO.
"""

import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from creditos.models import Credito, Cuota, EstadoSolicitud, Pago, Solicitud
from creditos.reglas import tasa_efectiva_anual
from nucleo.auditoria import registrar
from nucleo.cifrado import indice_ci, normalizar_ci
from nucleo.models import Cliente, ParametroMensual

# Parámetros de demo para el mes actual. TODOS SUPUESTO (fuentes vacías → la interfaz lo avisa).
# - tasa máxima 27,07 %: cifra publicada por la prensa (Última Hora) como tope de "noviembre";
#   el año no está confirmado y la página del BCP no se pudo leer. Hay que verificarla.
# - tasa nominal, % de cuota/ingreso y cargos: inventados para la demo; los reales los da Credisolución.
PARAMETROS_DEMO = {
    "tasa_maxima_anual": Decimal("0.2707"),
    "tasa_nominal_anual": Decimal("0.25"),
    "pct_max_cuota_ingreso": Decimal("0.30"),
    "cargos": [
        {"concepto": "Gastos administrativos (ejemplo)", "tipo": "inicial_pct", "valor": "0.02"},
        {"concepto": "Seguro de vida (ejemplo)", "tipo": "pct_saldo", "valor": "0.001"},
    ],
}

LOTE = 2000   # filas por INSERT (más rápido que una por una, sin agotar la memoria)


def _leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _fecha(texto: str, desplazamiento: timedelta) -> date | None:
    """'2026-01-15' → date desplazada; '' → None."""
    return date.fromisoformat(texto) + desplazamiento if texto else None


class Command(BaseCommand):
    help = "Carga clientes, créditos, cuotas y pagos sintéticos desde datos_generados/."

    def add_arguments(self, parser):
        parser.add_argument("--carpeta", type=Path, default=settings.CARPETA_SINTETICOS)
        parser.add_argument("--sin-desplazar", action="store_true", help="no mueve las fechas a hoy")
        parser.add_argument("--hoy", type=date.fromisoformat, default=None,
                            help="fecha que hace de 'hoy' (AAAA-MM-DD); por defecto, la del sistema")

    def handle(self, *args, **op):
        carpeta: Path = op["carpeta"]
        meta_ruta = carpeta / "meta.json"
        if not meta_ruta.exists():
            raise CommandError(f"No encuentro {meta_ruta}. Generá los datos: python -m datos_sinteticos.generar")
        if Cliente.objects.exclude(codigo_externo="").exists():
            raise CommandError("Ya hay datos sintéticos cargados. Para empezar de cero borrá la base "
                               "(SQLite: backend/db.sqlite3; Docker: docker compose down -v) y migrá de nuevo.")

        meta = json.loads(meta_ruta.read_text(encoding="utf-8"))
        hoy = op["hoy"] or date.today()
        corte = date.fromisoformat(meta["fecha_corte"])
        desplazamiento = timedelta(0) if op["sin_desplazar"] else hoy - corte

        self.stdout.write(f"Leyendo {carpeta} (corte {corte}, desplazamiento {desplazamiento.days} días)…")
        filas_clientes = _leer_csv(carpeta / "clientes.csv")
        filas_creditos = _leer_csv(carpeta / "creditos.csv")
        filas_cuotas = _leer_csv(carpeta / "cuotas.csv")
        filas_pagos = _leer_csv(carpeta / "pagos.csv")

        # Todo o nada: si algo falla a mitad de camino, no queda la base a medio cargar.
        with transaction.atomic():
            clientes = self._clientes(filas_clientes, desplazamiento)
            creditos = self._creditos(filas_creditos, filas_cuotas, clientes, desplazamiento)
            cuotas = self._cuotas(filas_cuotas, creditos, desplazamiento)
            pagos = self._pagos(filas_pagos, creditos, cuotas, desplazamiento)
            parametro_creado = self._parametros(hoy)
            registrar("sistema", "carga_sintetica", "Base", "datos_generados", {
                "clientes": len(clientes), "creditos": len(creditos), "cuotas": len(cuotas),
                "pagos": pagos, "semilla": meta["semilla"], "desplazamiento_dias": desplazamiento.days,
            })

        self.stdout.write(self.style.SUCCESS(
            f"Cargados: {len(clientes)} clientes, {len(creditos)} créditos, {len(cuotas)} cuotas, {pagos} pagos."
        ))
        if parametro_creado:
            self.stdout.write(self.style.WARNING(
                f"Se crearon parámetros SUPUESTOS para {hoy:%m/%Y}. Revisalos en /admin/ antes de mostrarlos."
            ))

    # --- Cada tabla ----------------------------------------------------------------------

    def _clientes(self, filas, desplazamiento) -> dict[str, Cliente]:
        objetos = {}
        for f in filas:
            ci = normalizar_ci(f["ci"])
            c = Cliente(
                codigo_externo=f["id"], ci=ci, ci_indice=indice_ci(ci),   # bulk_create no llama a save()
                nombres=f["nombres"], apellidos=f["apellidos"], telefono=f["telefono"], correo=f["correo"],
                sexo=f["sexo"], segmento=f["segmento"], sucursal=f["sucursal"], canal_origen="sucursal",
                empleador=f["empleador"], cargo=f["cargo"],
            )
            c.fecha_nacimiento = date.fromisoformat(f["fecha_nacimiento"])    # la edad no se desplaza
            c.fecha_ingreso_laboral = _fecha(f["fecha_ingreso_laboral"], desplazamiento)
            c.ingreso_mensual = int(f["ingreso_mensual"])
            objetos[f["id"]] = c
        Cliente.objects.bulk_create(objetos.values(), batch_size=LOTE)
        return objetos

    def _creditos(self, filas, filas_cuotas, clientes, desplazamiento) -> dict[str, Credito]:
        # Totales de cuotas por crédito, para el costo total y la tasa efectiva.
        totales: dict[str, list[int]] = {}
        for q in filas_cuotas:
            totales.setdefault(q["credito_id"], []).append(int(q["total"]))

        solicitudes, creditos = [], {}
        for f in filas:
            cliente = clientes[f["cliente_id"]]
            # El canal del cliente es el de su primer crédito.
            cliente.canal_origen = f["canal"]
            solicitud = Solicitud(
                cliente=cliente, monto_pedido=int(f["monto"]), plazo_meses=int(f["plazo_meses"]),
                canal=f["canal"], estado=EstadoSolicitud.APROBADA, ingreso_confirmado=cliente.ingreso_mensual,
            )
            solicitudes.append(solicitud)
            desembolso = _fecha(f["fecha_desembolso"], desplazamiento)
            pagos = totales[f["id"]]
            creditos[f["id"]] = Credito(
                codigo_externo=f["id"], solicitud=solicitud, monto=int(f["monto"]),
                plazo_meses=int(f["plazo_meses"]), tasa_nominal_anual=Decimal(f["tasa_nominal_anual"]),
                costo_total=sum(pagos), tasa_efectiva_anual=tasa_efectiva_anual(int(f["monto"]), pagos),
                fecha_desembolso=desembolso, cosecha=desembolso.strftime("%Y-%m"),   # bulk_create no llama a save()
                sucursal=f["sucursal"], segmento=f["segmento"], canal=f["canal"], estado=f["estado"],
            )
        Cliente.objects.bulk_update(clientes.values(), ["canal_origen"], batch_size=LOTE)
        Solicitud.objects.bulk_create(solicitudes, batch_size=LOTE)
        Credito.objects.bulk_create(creditos.values(), batch_size=LOTE)
        return creditos

    def _cuotas(self, filas, creditos, desplazamiento) -> dict[tuple[str, int], Cuota]:
        objetos = {}
        for f in filas:
            objetos[(f["credito_id"], int(f["numero"]))] = Cuota(
                credito=creditos[f["credito_id"]], numero=int(f["numero"]),
                vencimiento=_fecha(f["vencimiento"], desplazamiento), capital=int(f["capital"]),
                interes=int(f["interes"]), total=int(f["total"]), estado=f["estado"],
                fecha_pago=_fecha(f["fecha_pago"], desplazamiento),
            )
        # bulk_create devuelve los id en SQLite moderno y PostgreSQL: los pagos los necesitan.
        Cuota.objects.bulk_create(objetos.values(), batch_size=LOTE)
        return objetos

    def _pagos(self, filas, creditos, cuotas, desplazamiento) -> int:
        objetos = [
            Pago(
                codigo_externo=f["id"], credito=creditos[f["credito_id"]],
                cuota=cuotas[(f["credito_id"], int(f["cuota_numero"]))], fecha=_fecha(f["fecha"], desplazamiento),
                monto=int(f["monto"]), medio=f["medio"], registrado_por="carga_sintetica",
            )
            for f in filas
        ]
        Pago.objects.bulk_create(objetos, batch_size=LOTE)
        return len(objetos)

    def _parametros(self, hoy: date) -> bool:
        """Crea los parámetros SUPUESTOS del mes actual si no existen. Devuelve True si los creó."""
        _, creado = ParametroMensual.objects.get_or_create(mes=hoy.replace(day=1), defaults=PARAMETROS_DEMO)
        if creado:
            registrar("sistema", "parametros_creados", "ParametroMensual", hoy.strftime("%Y-%m"),
                      {"supuestos": True})
        return creado
