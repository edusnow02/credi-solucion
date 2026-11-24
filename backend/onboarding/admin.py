"""Administración del onboarding: solo consulta (los cambios pasan por los flujos, que auditan)."""

from django.contrib import admin

from onboarding.models import CampoExtraido, Documento


class CampoEnLinea(admin.TabularInline):
    model = CampoExtraido
    fields = ("nombre", "valor_ocr", "confianza", "motor", "estado", "observacion", "valor_confirmado")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "solicitud", "confianza_global", "reemplazado", "recibido")
    list_filter = ("tipo", "estado", "reemplazado")
    readonly_fields = [f.name for f in Documento._meta.fields if f.name != "texto_ocr"]
    exclude = ("texto_ocr",)   # el texto completo de la cédula no se muestra en el admin
    inlines = [CampoEnLinea]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
