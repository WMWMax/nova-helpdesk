from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Product(models.Model):
    users = models.ManyToManyField(User, verbose_name='Пользователи', related_name='products', blank=True)
    product_name = models.CharField(max_length=100, verbose_name='Наименование')
    product_serialnumber = models.CharField(max_length=50, verbose_name='Серийный номер',
                                            blank=True, null=True)
    product_date = models.DateField(verbose_name='Дата поставки', blank=True, null=True)
    product_address = models.TextField(verbose_name='Адрес размещения', blank=True, null=True)

    class Meta:
        db_table = 'products'
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
    

    def __str__(self):
        return self.product_name