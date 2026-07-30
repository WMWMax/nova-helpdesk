from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from products.models import Product

from datetime import datetime, timedelta
import random, string
import os
# Статусы заявки
TASK_STATUS = (
    ('NEW', 'Новый'),
    ('CLOSE', 'Закрыт'),
    ('END', 'Предоставлен'),
    ('REQ', 'Запрос'),
    ('WORK', 'В работе'),
    ('ANS', 'Уточнен'),
    ('REF','Отклонен')
)

# Приоритеты заявки
TASK_PRIO = (
    ('CRIT', 'Критический'),
    ('HIGH', 'Высокий'),
    ('LOW', 'Низкий'),
)

# Канал связи
TASK_COMM = (
    ('PHN', 'Телефон'),
    ('EML', 'Почта'),
    ('WEB', 'Веб'),
    ('BOT', 'Чат-бот'),
    ('MSG', 'Мессенджер')
)

def save_upload_file(instance, filename):
    return 'files/{0}/{1}'.format(instance.task_fk.id, filename)

def save_comment_file(instance, filename):
    return 'comments/{0}/{1}'.format(instance.task_fk.id, filename)

def save_comment_attachment(instance, filename):
    return 'comments/{0}/{1}'.format(instance.comment_fk.task_fk_id, filename)


def random_uuid():    
    letters = string.ascii_lowercase+string.digits
    return ''.join(random.choice(letters) for i in range(12))

# Основная модель заявки
class Task(models.Model):
    task_uuid = models.CharField(max_length=12, default=random_uuid, unique=True)
    task_subject = models.CharField(max_length=100, verbose_name='Тема заявки')
    task_createdate = models.DateTimeField(default=timezone.now, 
                                              verbose_name='Дата создания')
    task_startdate = models.DateTimeField(verbose_name='Дата начала', 
                                             blank=True, 
                                             null=True)
    task_enddate = models.DateTimeField(verbose_name='Дата окончания план',
                                           blank=True,
                                           null=True)
    task_fact_enddate = models.DateTimeField(verbose_name='Дата фактического окончания',
                                           blank=True,
                                           null=True)
    task_prio = models.CharField(max_length=4, choices=TASK_PRIO,
                                 verbose_name='Приоритет')
    task_status = models.CharField(max_length=5, choices=TASK_STATUS,
                                   verbose_name='Статус', default='NEW')
    task_product = models.ForeignKey(Product, default=None, verbose_name='КПО', 
                                     on_delete=models.SET_NULL, 
                                     blank=True, null=True,
                                     help_text='Компонент программного обеспечения')                                                                                                   
    task_text = models.TextField(verbose_name='Текст')    
    task_communication = models.CharField(max_length=5, verbose_name='Канал взаимодействия',
                                             default='WEB', choices=TASK_COMM)
    task_executor = models.ForeignKey(User, verbose_name='Исполнитель',
                                        blank=True,
                                        null=True,
                                        related_name='executor',
                                        on_delete=models.CASCADE)
    task_customer = models.ForeignKey(User, verbose_name='Заказчик',
                                        blank=True,
                                        null=True,
                                        related_name='customer',
                                        on_delete=models.CASCADE)
    task_close = models.BooleanField(default=False, verbose_name='Закрыта')
    
    class Meta:
        db_table = 'tasks'
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-task_createdate']

    def __str__(self):
        return '{}'.format(self.task_subject)

    def save(self, *args, **kwargs):
#        if self.task_prio == 'CRIT':
#            self.task_enddate = datetime.now() + timedelta(days=2)
#        elif self.task_prio == 'HIGH':
#            self.task_enddate = datetime.now() + timedelta(days=5)
#        else:
#            self.task_enddate = datetime.now() + timedelta(days=20)

        if self.task_prio == 'CRIT':
            self.task_enddate = self.task_createdate + timedelta(days=2)
        elif self.task_prio == 'HIGH':
            self.task_enddate = self.task_createdate + timedelta(days=5)
        else:
            self.task_enddate = self.task_createdate + timedelta(days=20)

        super().save(*args, **kwargs)


    def get_absolute_url(self):
        return reverse('view_task', args=[str(self.id)])

    def get_editable_url(self):
        return reverse('edit_task', args=[str(self.id)])

class TaskFiles(models.Model):
    task_fk = models.ForeignKey(Task, on_delete=models.CASCADE)
    task_file = models.FileField(upload_to=save_upload_file, 
                                    verbose_name='Файл')

    class Meta:
        db_table = 'tasks_files'
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'

    def get_file_url(self):
        return "/media/%s" % self.task_file

    def get_filename(self):
        filename = os.path.basename(self.task_file.name)
        return filename
    
    def get_filesize(self):
        try:
            file = os.path.join( 'media', str(self.task_file))
            return '{:.2f} Kb'.format(os.path.getsize(file) / 1024)
        except Exception as e:
            print(e)
        

    def get_icon_extension(self):
        name, extension = os.path.splitext(self.task_file.name)
        

        if extension in ['.pdf']:
            return 'pdf'
        elif extension in ['.doc', '.docx']:
            return 'word'
        elif extension in ['.xls', '.xlsx', '.csv']:
            return 'excel'
        elif extension in ['.png','.jpg']:
            return 'image'

        return 'alt'


class Solution(models.Model):
    solution_title = models.CharField(max_length=200, verbose_name='Заголовок')
    solution_problem = models.TextField(verbose_name='Описание проблемы')
    solution_text = models.TextField(verbose_name='Решение')
    solution_product = models.ForeignKey(Product, on_delete=models.SET_NULL,
                                         blank=True, null=True, verbose_name='КПО')

    class Meta:
        db_table = 'solutions'
        verbose_name = 'Типовое решение'
        verbose_name_plural = 'Типовые решения'

    def __str__(self):
        return self.solution_title


class TaskComment(models.Model):
    task_fk = models.ForeignKey(Task, on_delete=models.CASCADE)
    comment_author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    comment_text = models.TextField(verbose_name='Текст', blank=True)
    comment_file = models.FileField(upload_to=save_comment_file, blank=True, null=True, verbose_name='Вложение')
    comment_createdate = models.DateTimeField(default=timezone.now, verbose_name='Дата комментария')
    comment_isresult = models.BooleanField(default=False, verbose_name='Решение')

    class Meta:
        db_table = 'tasks_comments'
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Коментарии'
        ordering = ['-comment_isresult', 'comment_createdate']


class TaskCommentFile(models.Model):
    comment_fk = models.ForeignKey(TaskComment, on_delete=models.CASCADE, related_name='files')
    comment_file = models.FileField(upload_to=save_comment_attachment, verbose_name='Вложение')

    class Meta:
        db_table = 'tasks_comment_files'
        verbose_name = 'Вложение комментария'
        verbose_name_plural = 'Вложения комментариев'

    def get_file_url(self):
        return "/media/%s" % self.comment_file

    def get_filename(self):
        return os.path.basename(self.comment_file.name)
