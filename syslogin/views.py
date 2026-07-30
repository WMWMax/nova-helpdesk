from django.shortcuts import render, redirect
from django.contrib import auth
from nova.views import user_dashboard, admin_dashboard
# from django.contrib.auth.models import User
# from django.views.decorators.csrf import csrf_protect

def login(request):
    args = {}
    args['error'] = None
    if request.POST:
        username = request.POST.get('username', ' ')
        password = request.POST.get('password', ' ')        
        user = auth.authenticate(username=username, password=password)      
            
        if user is not None and user.is_active:
            auth.login(request, user)
            
            if user.is_staff:                
                return redirect("/admins/%d" % user.id)
            else:                
                return redirect("/users/%d" % user.id)
        else:
            args['error'] = 'Неверное имя или пароль'

    return render(request, "auth.html", args)


def logout(request):
    auth.logout(request)
    return redirect("/")
