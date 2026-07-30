"""nova URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views

urlpatterns = [
    path('create-task', views.create_task, name='create-task'),
    path('filter', views.filter_tasks, name='filter'),
    path('show/', views.show_all_tasks, name='show'),
    path('show/<int:task_id>', views.view_task, name='view_task'),    
    path('show/<int:task_id>/attach', views.attach_file, name='attach_file'),    
    path('show/<int:task_id>/add-comment', views.add_comment, name='add-comment'),
    path('show/<int:task_id>/accept/<int:comment_id>', views.accept_decision, name='accept'),
    path('show/<int:task_id>/comment/<int:comment_id>/delete', views.delete_comment, name='delete_comment'),
    path('show/<int:task_id>/comment/<int:comment_id>/edit', views.edit_comment, name='edit_comment'),
    path('show/<int:task_id>/take', views.take_task, name='take-task'),
    path('show/<int:task_id>/continue', views.continue_task, name='continue-task'),
    path('show/<int:task_id>/end', views.end_task, name='end-task'),
    path('show/<int:task_id>/close', views.close_task, name='close-task'),
    path('show/<int:task_id>/reopen', views.reopen_task, name='reopen-task'),
    path('show/<int:task_id>/delete/<int:file_id>', views.delete_file, name='delete_file'),
    path('edit/<int:task_id>', views.edit_task, name='edit_task'),
    path('show/<int:task_id>/assign', views.assign_executor, name='assign_executor'),
    path('upload-image', views.upload_editor_image, name='upload_editor_image'),
    path('products-for-customer', views.products_for_customer, name='products_for_customer'),
]
