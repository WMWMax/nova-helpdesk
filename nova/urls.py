# encodig: utf-8
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
import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.shortcuts import render
from django.http import HttpResponse

html_folder = os.path.join(settings.BASE_DIR, 'templates/docs/')

documentation_urls = [] + static(settings.DOCS_UPLOADS, document_root=settings.DOCS_ROOT_UPLOADS)

html_files = [f for f in os.listdir(html_folder) if f.endswith('.html')]

for html_file in html_files:
    file_name = os.path.splitext(html_file)[0].strip()
    documentation_urls.append(path(f'docs/{file_name}.html', lambda request, file_name=file_name: HttpResponse(render(request,  f'../templates/docs/{file_name}.html', {}))))

urlpatterns = [
    path('', views.index),
    path('check', views.check_my_task),
    path('admins/<int:user_id>', views.admin_dashboard),
    path('users/<int:user_id>', views.user_dashboard),
    path('report/', views.dump_report_to_excel),
    path('help/', views.help_view, name='help'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('database/', views.database_view, name='database'),
    path('tasks/', include('tasks.urls')),
    path('syslogin/', include('syslogin.urls')),
    path('profile/', include('profiles.urls')),
    path('chat/', include('chat.urls')),
    path('admin/', admin.site.urls),
    path('docs/', lambda request: HttpResponse(render(request, '../templates/docs/index.html'))),
    path('', include(documentation_urls)),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = views.handler_404
