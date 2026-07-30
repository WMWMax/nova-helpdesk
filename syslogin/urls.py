from django.urls import path 

from syslogin.views import login, logout
    # , logout


urlpatterns = [
    path('login', login, name='login'),
    path('logout', logout, name='logout'),
]