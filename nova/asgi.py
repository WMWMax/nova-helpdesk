"""
ASGI config for nova project.
Поддерживает HTTP (Django) и WebSocket (Channels).
"""

import os
import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nova.settings')
django.setup()

import chat.routing

application = ProtocolTypeRouter({
    # Обычные HTTP-запросы обрабатывает Django
    'http': get_asgi_application(),
    # WebSocket-запросы — через Channels с аутентификацией по сессии
    'websocket': AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})