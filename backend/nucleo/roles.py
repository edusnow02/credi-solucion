"""
Roles del personal (grupos de Django).

Los grupos se crean con una migración (nucleo/migrations/0002_roles.py), así existen en cualquier base.
"""

ANALISTA = "analista"
COBRANZAS = "cobranzas"
GERENCIA = "gerencia"

TODOS = (ANALISTA, COBRANZAS, GERENCIA)


def tiene_rol(usuario, *roles: str) -> bool:
    """¿El usuario está activo, entró con su sesión y pertenece a alguno de los roles?"""
    if not usuario or not usuario.is_authenticated or not usuario.is_active:
        return False
    return usuario.groups.filter(name__in=roles).exists()
