import os
from django.db import models
from django.contrib.auth.models import User


class ChatRoom(models.Model):
    """Личный диалог между двумя пользователями."""
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chatrooms_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chatrooms_as_user2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'

    def get_other_user(self, user):
        """Вернуть собеседника — того, кто не является текущим пользователем."""
        return self.user2 if self.user1 == user else self.user1

    @staticmethod
    def get_or_create_room(user_a, user_b):
        """Найти или создать диалог между двумя пользователями.
        Всегда сохраняем в канонической форме: меньший id — user1."""
        if user_a.id > user_b.id:
            user_a, user_b = user_b, user_a
        room, _ = ChatRoom.objects.get_or_create(user1=user_a, user2=user_b)
        return room


def chat_upload_path(instance, filename):
    return 'chat/{0}/{1}'.format(instance.room_id, filename)


class Message(models.Model):
    """Сообщение в диалоге."""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    body = models.TextField(verbose_name='Текст', blank=True)
    file = models.FileField(upload_to=chat_upload_path, blank=True, null=True, verbose_name='Файл')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')

    @property
    def file_basename(self):
        import os
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def file_is_image(self):
        if not self.file:
            return False
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp')

    @property
    def file_extension(self):
        if not self.file:
            return ''
        return os.path.splitext(self.file.name)[1].lstrip('.').upper()

    @property
    def file_size_display(self):
        if not self.file:
            return ''
        try:
            size = self.file.size
        except (OSError, ValueError):
            return ''
        if size < 1024:
            return '{} B'.format(size)
        elif size < 1024 * 1024:
            return '{:.0f} KB'.format(size / 1024)
        return '{:.1f} MB'.format(size / (1024 * 1024))

    FILE_ICONS = {
        '.pdf': 'fa-file-pdf',
        '.doc': 'fa-file-word', '.docx': 'fa-file-word',
        '.xls': 'fa-file-excel', '.xlsx': 'fa-file-excel', '.csv': 'fa-file-excel',
        '.ppt': 'fa-file-powerpoint', '.pptx': 'fa-file-powerpoint',
        '.zip': 'fa-file-archive', '.rar': 'fa-file-archive', '.7z': 'fa-file-archive',
        '.mp3': 'fa-file-audio', '.wav': 'fa-file-audio',
        '.mp4': 'fa-file-video', '.mov': 'fa-file-video', '.avi': 'fa-file-video',
        '.txt': 'fa-file-alt',
    }

    @property
    def file_icon(self):
        if not self.file:
            return 'fa-file'
        ext = os.path.splitext(self.file.name)[1].lower()
        return self.FILE_ICONS.get(ext, 'fa-file')

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
