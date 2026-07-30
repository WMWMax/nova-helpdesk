import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import ChatRoom, Message


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket-консьюмер для страницы конкретного диалога."""

    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        other_user_id = self.scope['url_route']['kwargs']['user_id']

        try:
            other_user = await database_sync_to_async(User.objects.get)(id=other_user_id)
        except User.DoesNotExist:
            await self.close()
            return

        self.other_user_id = other_user.id

        room = await database_sync_to_async(ChatRoom.get_or_create_room)(self.user, other_user)
        self.room_id = room.id

        ids = sorted([self.user.id, other_user.id])
        self.room_group_name = f'chat_{ids[0]}_{ids[1]}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Сообщаем другому участнику, что мы открыли чат и прочитали его сообщения
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'messages_read',
                'reader_id': self.user.id,
            }
        )

    async def disconnect(self, code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type', 'message')

        # Получатель сигналит, что прочитал новые сообщения (они уже видны на экране)
        if msg_type == 'mark_read':
            await database_sync_to_async(
                lambda: Message.objects.filter(
                    room_id=self.room_id, is_read=False
                ).exclude(sender=self.user).update(is_read=True)
            )()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read',
                    'reader_id': self.user.id,
                }
            )
            return

        # Обычное текстовое сообщение
        body = data.get('message', '').strip()
        if not body:
            return

        msg = await database_sync_to_async(Message.objects.create)(
            room_id=self.room_id,
            sender=self.user,
            body=body,
        )

        sender_name = self.user.get_full_name() or self.user.username

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': body,
                'sender_id': self.user.id,
                'sender_name': sender_name,
                'timestamp': msg.timestamp.strftime('%H:%M'),
            }
        )

        # Уведомляем получателя, если он на другой странице
        await self.channel_layer.group_send(
            f'notify_{self.other_user_id}',
            {
                'type': 'new_message_notification',
                'sender_id': self.user.id,
                'sender_name': sender_name,
                'preview': body[:100],
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def messages_read(self, event):
        """Собеседник прочитал сообщения — отправляем сигнал отправителю обновить галочки."""
        # Отправляем только тому, чьи сообщения прочитали (не читателю)
        if self.user.id != event['reader_id']:
            await self.send(text_data=json.dumps({'type': 'messages_read'}))


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket для глобальных уведомлений — открыт на каждой странице сайта."""

    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f'notify_{self.user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def new_message_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'preview': event['preview'],
        }))