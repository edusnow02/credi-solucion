"""
Genera clientes ficticios.

Cada cliente es una ficha (dataclass) con los mismos datos que tendrá el modelo Cliente en la Fase 2,
más los datos laborales que después aparecen en los documentos (empleador, salario, antigüedad).
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from datos_sinteticos import catalogos, supuestos
from datos_sinteticos.azar import elegir_con_peso, redondear_a_mil


@dataclass
class Persona:
    id: str                    # identificador estable dentro de los datos sintéticos (C00001…)
    ci: int                    # cédula ficticia (solo números)
    nombres: str
    apellidos: str
    sexo: str                  # "F" o "M"; SOLO para medir sesgo, nunca para el score
    fecha_nacimiento: date
    segmento: str              # clave de supuestos.SEGMENTOS
    sucursal: str
    telefono: str
    correo: str
    ingreso_mensual: int       # G.; salario en segmentos con liquidación, declarado en los demás
    empleador: str             # vacío si el segmento no tiene empleador
    cargo: str
    fecha_ingreso_laboral: date | None   # None si no hay empleador

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"

    def edad_en(self, fecha: date) -> int:
        """Edad cumplida en una fecha dada."""
        # Restamos un año si todavía no llegó el cumpleaños en ese año.
        antes_del_cumple = (fecha.month, fecha.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        return fecha.year - self.fecha_nacimiento.year - int(antes_del_cumple)

    def antiguedad_meses_en(self, fecha: date) -> int | None:
        """Meses completos trabajando para el empleador actual en una fecha dada."""
        if self.fecha_ingreso_laboral is None:
            return None
        meses = (fecha.year - self.fecha_ingreso_laboral.year) * 12 + (fecha.month - self.fecha_ingreso_laboral.month)
        if fecha.day < self.fecha_ingreso_laboral.day:
            meses -= 1
        return max(meses, 0)


def formatear_ci(ci: int) -> str:
    """91234567 → '91.234.567' (formato paraguayo con puntos de miles)."""
    return f"{ci:,}".replace(",", ".")


def _ci_unicas(rng: random.Random, cantidad: int) -> list[int]:
    """Elige 'cantidad' CI distintas dentro del rango ficticio."""
    # sample garantiza que no se repitan; range no ocupa memoria aunque sea enorme.
    return rng.sample(range(supuestos.CI_MINIMA, supuestos.CI_MAXIMA + 1), cantidad)


def _fecha_nacimiento(rng: random.Random, edad_min: int, edad_max: int) -> date:
    """Fecha de nacimiento para que al corte la persona tenga entre edad_min y edad_max años."""
    edad = rng.randint(edad_min, edad_max)
    corte = supuestos.FECHA_CORTE
    # Partimos del día en que cumplió 'edad' años justo en la fecha de corte y retrocedemos entre
    # 0 y 364 días: así al corte tiene exactamente 'edad' años y no todos cumplen el mismo día.
    # (La fecha de corte no es 29 de febrero, así que esa fecha existe en cualquier año.)
    cumple_en_el_corte = date(corte.year - edad, corte.month, corte.day)
    return cumple_en_el_corte - timedelta(days=rng.randint(0, 364))


def _nombres(rng: random.Random, sexo: str) -> str:
    """Uno o dos nombres de pila (en Paraguay es muy común llevar dos)."""
    lista = catalogos.NOMBRES_FEMENINOS if sexo == "F" else catalogos.NOMBRES_MASCULINOS
    if rng.random() < 0.6:
        primero, segundo = rng.sample(lista, 2)
        return f"{primero} {segundo}"
    return rng.choice(lista)


def _datos_laborales(rng: random.Random, segmento: str) -> tuple[str, str, date | None]:
    """Devuelve (empleador, cargo, fecha de ingreso) según el segmento."""
    if segmento == "ips":
        empleador = rng.choice(catalogos.EMPRESAS_FICTICIAS)
        cargo = rng.choice(catalogos.CARGOS_PRIVADOS)
    elif segmento == "funcionario":
        empleador = rng.choice(catalogos.INSTITUCIONES_FICTICIAS)
        cargo = rng.choice(catalogos.CARGOS_PUBLICOS)
    elif segmento == "jubilado":
        # El jubilado cobra de una caja, pero no tiene "antigüedad laboral" que evaluar.
        return catalogos.PAGADOR_JUBILACIONES, "Jubilado", None
    else:
        return "", "", None
    # Antigüedad entre 3 meses y 20 años antes del corte (distribución sesgada hacia lo reciente:
    # el cuadrado de un número entre 0 y 1 cae más seguido cerca de 0).
    meses = 3 + int((rng.random() ** 2) * 237)
    fecha_ingreso = supuestos.FECHA_CORTE - timedelta(days=int(meses * 30.4))
    return empleador, cargo, fecha_ingreso


def generar_personas(rng: random.Random, cantidad: int) -> list[Persona]:
    """Genera 'cantidad' clientes ficticios."""
    cis = _ci_unicas(rng, cantidad)
    pesos_segmentos = {clave: datos["peso"] for clave, datos in supuestos.SEGMENTOS.items()}
    personas = []
    for indice, ci in enumerate(cis, start=1):
        segmento = elegir_con_peso(rng, pesos_segmentos)
        datos_segmento = supuestos.SEGMENTOS[segmento]
        sexo = rng.choice(["F", "M"])
        # Ingreso: un valor al azar dentro del rango del segmento, en salarios mínimos.
        sm_min, sm_max = datos_segmento["ingreso_sm"]
        ingreso = redondear_a_mil(rng.uniform(sm_min, sm_max) * supuestos.SALARIO_MINIMO)
        empleador, cargo, fecha_ingreso = _datos_laborales(rng, segmento)
        personas.append(
            Persona(
                id=f"C{indice:05d}",
                ci=ci,
                nombres=_nombres(rng, sexo),
                apellidos=" ".join(rng.sample(catalogos.APELLIDOS, 2)),
                sexo=sexo,
                fecha_nacimiento=_fecha_nacimiento(rng, *datos_segmento["edad"]),
                segmento=segmento,
                sucursal=elegir_con_peso(rng, supuestos.SUCURSALES),
                telefono=f"{supuestos.PREFIJO_TELEFONO_FICTICIO} {rng.randint(100, 999)} {rng.randint(100, 999)}",
                correo=f"cliente{indice:05d}@{supuestos.DOMINIO_CORREO_FICTICIO}",
                ingreso_mensual=ingreso,
                empleador=empleador,
                cargo=cargo,
                fecha_ingreso_laboral=fecha_ingreso,
            )
        )
    return personas
