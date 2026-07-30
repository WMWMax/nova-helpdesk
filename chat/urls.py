from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox_view, name='chat_inbox'),
    path('<int:user_id>/', views.room_view, name='chat_room'),
    path('<int:user_id>/upload/', views.chat_upload, name='chat_upload'),
]