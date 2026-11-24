"""
Listas de palabras para armar personas y empresas ficticias.

- Nombres y apellidos: comunes en Paraguay. Al combinarlos al azar con una CI ficticia,
  no describen a ninguna persona real.
- Empleadores: INVENTADOS. Si alguno coincide con una empresa real, es casualidad;
  avisar y se cambia. No se usan nombres de empresas ni instituciones reales.
"""

NOMBRES_FEMENINOS = [
    "María", "Ana", "Rosa", "Liz", "Gloria", "Sonia", "Patricia", "Carmen", "Mirian", "Lourdes",
    "Nilda", "Graciela", "Fátima", "Celeste", "Leticia", "Natalia", "Andrea", "Romina", "Paola",
    "Rocío", "Belén", "Fabiola", "Mónica", "Dahiana", "Noelia", "Sandra", "Elena", "Cinthia",
    "Lorena", "Ramona", "Juana", "Teresa", "Victoria", "Alejandra", "Gabriela", "Diana",
]

NOMBRES_MASCULINOS = [
    "Juan", "Carlos", "José", "Luis", "Jorge", "Víctor", "Ramón", "Pedro", "Hugo", "Miguel",
    "Fernando", "Óscar", "Derlis", "Néstor", "Arnaldo", "Rubén", "Gustavo", "Marcelo", "Diego",
    "Rodrigo", "Andrés", "Fabián", "Julio", "César", "Enrique", "Mario", "Antonio", "Francisco",
    "Ricardo", "Sergio", "Daniel", "Alcides", "Celso", "Blas", "Osvaldo", "Hernán",
]

APELLIDOS = [
    "González", "Benítez", "Martínez", "López", "Giménez", "Ortiz", "Duarte", "Villalba", "Cáceres",
    "Ramírez", "Rojas", "Báez", "Acosta", "Fernández", "Aquino", "Ayala", "Vera", "Gómez", "Torres",
    "Romero", "Sosa", "Ruiz Díaz", "Núñez", "Cabrera", "Cardozo", "Escobar", "Franco", "Galeano",
    "Insfrán", "Ledesma", "Medina", "Ojeda", "Paredes", "Riveros", "Salinas", "Talavera",
    "Valdez", "Zárate", "Brítez", "Caballero", "Espínola", "Florentín", "Maidana", "Peralta",
]

# Empresas privadas ficticias (empleadores de asalariados con IPS).
EMPRESAS_FICTICIAS = [
    "Distribuidora Tajy Poty S.A.",
    "Industrias Arasa Morotĩ S.R.L.",
    "Transportes Ñandutí Rapé S.A.",
    "Supermercados Kokue Guasu S.A.",
    "Constructora Ita Pyahu S.A.",
    "Frigorífico Mbokaja Verde S.A.",
    "Servicios Generales Yvoty S.R.L.",
    "Textil Algodón del Sur Ficticia S.A.",
    "Comercial Tres Arroyos Ejemplo S.A.",
    "Logística Paraná Simulada S.A.",
    "Laboratorio Pyhare Sano S.A.",
    "Seguridad Privada Mborayhu S.R.L.",
]

# Instituciones públicas ficticias (empleadores de funcionarios).
INSTITUCIONES_FICTICIAS = [
    "Dirección Nacional de Ejemplo",
    "Secretaría de Servicios Simulados",
    "Ente Regulador Ficticio",
    "Municipalidad de Villa Ejemplo",
    "Hospital Regional Simulado",
    "Escuela Pública Demostrativa N.º 100",
]

# Pagador de jubilaciones: genérico, para no usar el nombre de una caja real.
PAGADOR_JUBILACIONES = "Caja de Jubilaciones (ficticia)"

# Cargos para la liquidación de sueldo.
CARGOS_PRIVADOS = ["Vendedor", "Cajero", "Auxiliar administrativo", "Chofer", "Operario",
                   "Repositor", "Recepcionista", "Técnico", "Supervisor", "Guardia"]
CARGOS_PUBLICOS = ["Auxiliar", "Docente", "Enfermero", "Técnico", "Administrativo", "Jefe de sección"]
