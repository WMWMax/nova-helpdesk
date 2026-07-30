from django.db.models import Q
from .models import Message


def unread_chat_count(request):
    """Добавляет в контекст каждого шаблона число непрочитанных сообщений."""
    if not request.user.is_authenticated:
        return {'unread_chat_count': 0}
    count = Message.objects.filter(
        Q(room__user1=request.user) | Q(room__user2=request.user),
        is_read=False
    ).exclude(sender=request.user).count()
    return {'unread_chat_count': count}