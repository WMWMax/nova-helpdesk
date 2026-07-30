from django.urls import path
from . import views

urlpatterns = [
    path('', views.profile_view, name='profile'),
    path('<int:user_id>/', views.user_profile_view, name='user_profile'),
]
