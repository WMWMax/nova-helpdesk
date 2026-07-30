from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    filter_horizontal = ('users',)
    list_display = ('product_name', 'product_serialnumber', 'get_users')

    def get_users(self, obj):
        return ', '.join(str(u) for u in obj.users.all())
    get_users.short_description = 'Пользователи'
