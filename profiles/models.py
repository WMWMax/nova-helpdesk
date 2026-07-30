from django.db import models
from django.contrib.auth.models import User


def avatar_upload_path(instance, filename):
    return 'avatars/{0}/{1}'.format(instance.user.id, filename)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True, verbose_name='Фото профиля')
    phone = models.CharField(max_length=50, blank=True, null=True, verbose_name='Телефон')
    messenger = models.CharField(max_length=100, blank=True, null=True, verbose_name='Мессенджер')
    extra_email = models.EmailField(blank=True, null=True, verbose_name='Дополнительная почта')
    show_phone = models.BooleanField(default=True, verbose_name='Показывать телефон')
    show_messenger = models.BooleanField(default=True, verbose_name='Показывать мессенджер')
    show_extra_email = models.BooleanField(default=True, verbose_name='Показывать доп. почту')

    class Meta:
        db_table = 'profiles'
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return 'Профиль {}'.format(self.user)
