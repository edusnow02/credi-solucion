"""Panel de administración para créditos (solo consulta en el prototipo)."""

from django.contrib import admin

from creditos.models import Credito, Pagare, Pago, Solicitud


class SoloLectura(admin.ModelAdmin):
    """Los cambios se hacen por los flujos del sistema (que dejan auditoría), no a mano en el admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Solicitud)
class SolicitudAdmin(SoloLectura):
    list_display = ("__str__", "monto_pedido", "plazo_meses", "canal", "estado", "creada")
    list_filter = ("estado", "canal")


@admin.register(Credito)
class CreditoAdmin(SoloLectura):
    list_display = ("__str__", "cosecha", "sucursal", "segmento", "canal", "estado")
    list_filter = ("estado", "segmento", "sucursal", "canal", "cosecha")


@admin.register(Pago)
class PagoAdmin(SoloLectura):
    list_display = ("__str__", "credito", "medio", "registrado_por")
    list_filter = ("medio",)


@admin.register(Pagare)
class PagareAdmin(SoloLectura):
    list_display = ("__str__", "estado", "emitido")
