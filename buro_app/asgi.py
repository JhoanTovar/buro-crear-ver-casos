"""
ASGI config for buro_app project.
Sistema de Gestion de Consultorio Juridico - Buro Legal
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buro_app.settings')

application = get_asgi_application()
