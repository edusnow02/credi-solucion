"""
Direcciones del backend.

Parte 2A: solo el panel de administración de Django (/admin/), útil para que Edu mire los datos
y cargue parámetros. La API interna, el panel del analista y la API de clientes llegan después.
"""

from django.contrib import admin
from django.urls import path

admin.site.site_header = "Credisolución — administración (prototipo)"
admin.site.site_title = "Credisolución prototipo"

urlpatterns = [
    path("admin/", admin.site.urls),
]
