"""
Panel de administración de Django (/admin/), para que Edu mire los datos y cargue parámetros.
No es el panel del analista (ese llega en la Parte 2C).

Reglas: la auditoría se puede leer pero no tocar; los clientes no se borran desde acá.
"""

from django.contrib import admin

from nucleo.models import Cliente, CuentaCliente, EventoAuditoria, ParametroMensual


@admin.register(ParametroMensual)
class ParametroMensualAdmin(admin.ModelAdmin):
    list_display = ("mes", "tasa_maxima_anual", "tasa_nominal_anual", "pct_max_cuota_ingreso", "supuestos")
    readonly_fields = ("actualizado", "actualizado_por")

    @admin.display(description="valores SUPUESTOS")
    def supuestos(self, obj):
        return ", ".join(obj.campos_supuestos) or "—"

    def save_model(self, request, obj, form, change):
        # Guardamos quién cambió los parámetros.
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    # Los campos cifrados no se pueden buscar ni ordenar en la base: solo mostramos columnas seguras.
    list_display = ("__str__", "segmento", "sucursal", "canal_origen", "creado")
    list_filter = ("segmento", "sucursal", "canal_origen")
    readonly_fields = ("ci_indice", "creado")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "actor", "accion", "entidad", "entidad_id")
    list_filter = ("accion", "entidad")

    # Solo lectura: ni agregar, ni cambiar, ni borrar.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CuentaCliente)
class CuentaClienteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "activa", "ultimo_ingreso")
    readonly_fields = ("pin_hash",)
