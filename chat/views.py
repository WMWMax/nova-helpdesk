from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth.models import User
from django.db.models import Q, Max
from django.http import JsonResponse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import ChatRoom, Message
from nova.views import get_auth_user
import os


@login_required(login_url="/syslogin/login")
@never_cache
def inbox_view(request):
    """Список всех диалогов текущего пользователя."""
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    # Все комнаты, где участвует текущий пользователь, отсортированные по последнему сообщению
    rooms = ChatRoom.objects.filter(
        Q(user1=user) | Q(user2=user)
    ).annotate(
        last_message_time=Max('messages__timestamp')
    ).filter(last_message_time__isnull=False).order_by('-last_message_time')

    dialogs = []
    for room in rooms:
        other_user = room.get_other_user(user)
        unread = room.messages.filter(is_read=False).exclude(sender=user).count()
        last_msg = room.messages.order_by('-timestamp').first()
        dialogs.append({
            'room': room,
            'other_user': other_user,
            'unread': unread,
            'last_msg': last_msg,
        })

    args['dialogs'] = dialogs

    # Кому можно написать: заказчик видит только сотрудников, сотрудник — всех
    if user.is_staff:
        args['available_users'] = User.objects.filter(is_active=True).exclude(id=user.id).order_by('last_name', 'first_name')
    else:
        args['available_users'] = User.objects.filter(is_active=True, is_staff=True).order_by('last_name', 'first_name')

    return render(request, 'chat/inbox.html', args)


@login_required(login_url="/syslogin/login")
@never_cache
def room_view(request, user_id):
    """Страница конкретного диалога с пользователем user_id."""
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    other_user = get_object_or_404(User, id=user_id)

    # Нельзя написать самому себе
    if other_user == user:
        return redirect('chat_inbox')

    room = ChatRoom.get_or_create_room(user, other_user)

    # Помечаем входящие сообщения как прочитанные
    room.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

    chat_messages = room.messages.order_by('timestamp')

    args['other_user'] = other_user
    args['room'] = room
    args['chat_messages'] = chat_messages
    return render(request, 'chat/room.html', args)


@login_required(login_url="/syslogin/login")
def chat_upload(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return JsonResponse({'error': 'cannot message yourself'}, status=400)

    file = request.FILES.get('file')
    body = request.POST.get('body', '').strip()

    if not file and not body:
        return JsonResponse({'error': 'empty'}, status=400)

    room = ChatRoom.get_or_create_room(request.user, other_user)
    msg = Message.objects.create(room=room, sender=request.user, body=body, file=file)

    file_url  = msg.file.url if msg.file else None
    file_name = os.path.basename(msg.file.name) if msg.file else None
    file_size = msg.file_size_display if msg.file else None

    channel_layer = get_channel_layer()
    ids = sorted([request.user.id, other_user.id])
    group = f'chat_{ids[0]}_{ids[1]}'
    sender_name = request.user.get_full_name() or request.user.username

    async_to_sync(channel_layer.group_send)(group, {
        'type': 'chat_message',
        'message': body,
        'sender_id': request.user.id,
        'sender_name': sender_name,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'file_url': file_url,
        'file_name': file_name,
        'file_size': file_size,
    })

    async_to_sync(channel_layer.group_send)(f'notify_{other_user.id}', {
        'type': 'new_message_notification',
        'sender_id': request.user.id,
        'sender_name': sender_name,
        'preview': f'📎 {file_name}' if file_name else body[:100],
    })

    return JsonResponse({'success': True, 'file_url': file_url, 'file_name': file_name})
