from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Чат между двумя конкретными пользователями
    re_path(r'ws/chat/(?P<user_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    # Глобальные уведомления — открыт на каждой странице
    re_path(r'ws/notify/$', consumers.NotificationConsumer.as_asgi()),
]