from django.db import models
from tasks.models import Task
from django.contrib.auth.models import User

# Create your models here.

class History(models.Model):
    task_fk = models.ForeignKey(Task, verbose_name='Задача', on_delete=models.CASCADE)
    user_fk = models.ForeignKey(User, verbose_name='Пользователь', null=True, on_delete=models.SET_NULL)
    history_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата/Время')
    history_text = models.CharField(max_length=500, verbose_name='Изменение')

    class Meta:
        db_table = 'history'
        verbose_name = 'История изменений'
        verbose_name_plural = 'Истории изменений'
        ordering = ['-history_date']
    
