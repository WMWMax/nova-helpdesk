import re
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from nova.views import get_auth_user
from .models import Profile


@login_required(login_url="/syslogin/login")
def profile_view(request):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    profile, _ = Profile.objects.get_or_create(user=user)
    args['profile'] = profile

    if request.method == 'POST':
        phone_raw = re.sub(r'\D', '', request.POST.get('phone', ''))
        # Если пользователь ничего не ввёл — маска IMask оставляет только «7», сбрасываем
        phone_digits = phone_raw if len(phone_raw) > 1 else ''
        extra_email = request.POST.get('extra_email', '').strip()

        errors = []

        if phone_digits and (len(phone_digits) != 11 or not phone_digits.startswith('7')):
            errors.append('Введите корректный номер телефона.')

        if extra_email:
            if re.search(r'[а-яёА-ЯЁ]', extra_email):
                errors.append('Кириллица не может использоваться в адресе электронной почты. Введите адрес латинскими буквами (например: example@mail.ru).')
            elif extra_email.endswith('.'):
                errors.append('После точки в адресе должны быть символы (например: example@mail.ru).')
            elif re.search(r'(?i)(^|\.)xn--', extra_email.split('@')[-1]):
                errors.append('Адрес не должен содержать punycode-домен (xn--...). Введите адрес латинскими буквами (например: example@mail.ru).')
            else:
                try:
                    validate_email(extra_email)
                except ValidationError:
                    errors.append('Введите корректный email-адрес (например: example@mail.ru).')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'profiles/profile.html', args)

        profile.phone = phone_digits or None
        profile.messenger = request.POST.get('messenger', '').strip() or None
        profile.extra_email = extra_email or None
        profile.show_phone = 'show_phone' in request.POST
        profile.show_messenger = 'show_messenger' in request.POST
        profile.show_extra_email = 'show_extra_email' in request.POST

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']

        profile.save()
        messages.success(request, 'Профиль успешно сохранён!')
        return redirect('profile')

    return render(request, 'profiles/profile.html', args)


@login_required(login_url="/syslogin/login")
def user_profile_view(request, user_id):
    args = {}
    args.update(get_auth_user(request))
    target_user = User.objects.get(id=user_id)
    profile, _ = Profile.objects.get_or_create(user=target_user)
    args['target_user'] = target_user
    args['target_profile'] = profile
    return render(request, 'profiles/user_profile.html', args)
