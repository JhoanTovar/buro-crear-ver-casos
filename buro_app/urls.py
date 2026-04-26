"""
URL configuration for buro_app project.
Sistema de Gestion de Consultorio Juridico - Buro Legal
"""
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('', include('consultorio.urls')),
    path('admin/', admin.site.urls),
    
]
