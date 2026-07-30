import re
import bleach
from bleach.css_sanitizer import CSSSanitizer
from urllib.parse import urlencode
from django.shortcuts import render, redirect, Http404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from tasks.models import Task, TaskFiles, TaskComment, TaskCommentFile
from history.models import History
from nova.views import get_auth_user, send_email_notification
from nova.settings import EMAIL_HOST_USER

from datetime import datetime
from products.models import Product
# Create your views here.

# Теги/атрибуты, которые реально может произвести редактор Trumbowyg
# (см. кнопки в create_task.html/view_task.html). Всё остальное (включая
# <script>, on*-атрибуты, произвольный style) вырезается — поле task_text/
# comment_text рендерится в шаблонах с `|safe`, поэтому чистить нужно на входе.
_RICH_TEXT_TAGS = [
    'p', 'br', 'div', 'span', 'small', 'blockquote',
    'strong', 'b', 'em', 'i', 'u', 'del', 's', 'sup', 'sub',
    'ul', 'ol', 'li', 'hr', 'img',
]
_TEXT_ALIGN_RE = re.compile(r'^\s*text-align\s*:\s*(left|right|center|justify)\s*;?\s*$', re.IGNORECASE)
_CURSOR_POINTER_RE = re.compile(r'^\s*cursor\s*:\s*pointer\s*;?\s*$', re.IGNORECASE)
_RICH_TEXT_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=['text-align', 'cursor'])


def _rich_text_attr_filter(tag, name, value):
    if name == 'style':
        if tag == 'blockquote' and _CURSOR_POINTER_RE.match(value):
            return True
        return bool(_TEXT_ALIGN_RE.match(value))
    if tag == 'img' and name in ('src', 'alt'):
        return True
    if tag == 'blockquote' and name == 'data-reply-id':
        return True
    return False


def sanitize_rich_text(value):
    """Санитизирует HTML из редактора Trumbowyg перед сохранением в БД."""
    return bleach.clean(
        value or '',
        tags=_RICH_TEXT_TAGS,
        attributes=_rich_text_attr_filter,
        protocols=['http', 'https'],
        css_sanitizer=_RICH_TEXT_CSS_SANITIZER,
        strip=True,
    )

REPLY_BLOCKQUOTE_RE = re.compile(
    r'<blockquote data-reply-id="(\d+)" style="cursor:pointer;">.*?</blockquote>',
    re.DOTALL
)


def resolve_deleted_replies(comment_text, existing_comment_ids):
    """Заменяет цитаты на удалённые комментарии плейсхолдером."""
    def _replace(match):
        reply_id = int(match.group(1))
        if reply_id in existing_comment_ids:
            return match.group(0)
        return ('<blockquote style="cursor:default;">'
                '<small class="reply-author"><em>Комментарий был удалён</em></small>'
                '</blockquote>')
    return REPLY_BLOCKQUOTE_RE.sub(_replace, comment_text)

STATUS_LABELS = {
    'NEW': 'Новый',
    'WORK': 'В работе',
    'REQ': 'Уточнение',
    'ANS': 'Уточнен',
    'END': 'Предоставлен',
    'CLOSE': 'Закрыт',
    'REF': 'Отклонен',
}

def create_update_task(data):
    if 'task_text' in data:
        data['task_text'] = sanitize_rich_text(data['task_text'])
    task, created = Task.objects.update_or_create(id=data['id'], defaults=data)

    return task

def send_status_change_email(request, task, old_status, new_status, recipients):
    if not recipients:
        return
    task_url = request.build_absolute_uri(task.get_absolute_url())
    old_label = STATUS_LABELS.get(old_status, old_status)
    new_label = STATUS_LABELS.get(new_status, new_status)
    html_msg = """
    <h3>Изменение статуса заявки #{id}</h3>
    <p><b>Тема:</b> {subject}</p>
    <p><b>Статус изменён:</b> {old} → <b>{new}</b></p>
    <hr>
    <p><a href="{url}">Открыть заявку</a></p>
    """.format(id=task.id, subject=task.task_subject,
               old=old_label, new=new_label, url=task_url)
    mail_context = {
        'subject': 'Статус заявки #{} изменён: {} → {}'.format(task.id, old_label, new_label),
        'msg': 'Статус заявки #{} «{}» изменён: {} → {}'.format(task.id, task.task_subject, old_label, new_label),
        'html_msg': html_msg,
        'recepients': recipients,
    }
    send_email_notification(mail_context)

def add_history(**data):
    try:
        history = History.objects.create(**data)
        history.save()

        return True

    except Exception as e:
        print(e)

        return False
 
    


@login_required(login_url="/syslogin/login")
@never_cache
def show_all_tasks(request):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    if user.is_staff:
        if user.is_superuser:
            all_tasks = Task.objects.all()
        else:
            all_tasks = Task.objects.filter(task_executor=None) | \
                        Task.objects.filter(task_executor=user).exclude(task_status='CLOSE')
    else:
        all_tasks = Task.objects.filter(task_customer=user)

    subject = request.GET.get('subject', '').strip()
    statuses = request.GET.getlist('status')
    prios = request.GET.getlist('prio')
    executor = request.GET.get('executor', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if subject:
        all_tasks = all_tasks.filter(task_subject__icontains=subject)
    if statuses:
        all_tasks = all_tasks.filter(task_status__in=statuses)
    if prios:
        all_tasks = all_tasks.filter(task_prio__in=prios)
    if executor:
        all_tasks = all_tasks.filter(
            Q(task_executor__first_name__icontains=executor) |
            Q(task_executor__last_name__icontains=executor) |
            Q(task_executor__username__icontains=executor)
        )
    try:
        if date_from:
            datetime.strptime(date_from, '%Y-%m-%d')
            all_tasks = all_tasks.filter(task_createdate__date__gte=date_from)
    except ValueError:
        date_from = ''
    try:
        if date_to:
            datetime.strptime(date_to, '%Y-%m-%d')
            all_tasks = all_tasks.filter(task_createdate__date__lte=date_to)
    except ValueError:
        date_to = ''

    args['selected_subject'] = subject
    args['selected_statuses'] = statuses
    args['selected_prios'] = prios
    args['selected_executor'] = executor
    args['selected_date_from'] = date_from
    args['selected_date_to'] = date_to

    active_statuses = ['NEW', 'WORK', 'REQ', 'ANS']
    completed_statuses = ['END', 'CLOSE', 'REF']

    active_tasks    = all_tasks.filter(task_status__in=active_statuses)
    completed_tasks = all_tasks.filter(task_status__in=completed_statuses)

    active_paginator    = Paginator(active_tasks, 15)
    completed_paginator = Paginator(completed_tasks, 15)

    get_params = request.GET.copy()
    get_params.pop('page_active', None)
    get_params.pop('page_completed', None)

    args['active_page']    = active_paginator.get_page(request.GET.get('page_active', 1))
    args['completed_page'] = completed_paginator.get_page(request.GET.get('page_completed', 1))
    args['active_count']   = active_tasks.count()
    args['completed_count'] = completed_tasks.count()
    args['get_params']     = get_params.urlencode()

    return render(request, 'show_tasks.html', args)

@login_required(login_url="/syslogin/login")
def filter_tasks(request):
    return redirect(show_all_tasks)


@login_required(login_url="/syslogin/login")
@never_cache
def view_task(request, task_id):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    if user.is_staff:
        task = Task.objects.get(id=task_id)
    else:
        try:
            task = Task.objects.get(id=task_id, task_customer=user)
        except:
            raise Http404

    comments = list(TaskComment.objects.filter(task_fk=task))
    existing_comment_ids = {c.id for c in comments}
    for c in comments:
        c.comment_text = resolve_deleted_replies(c.comment_text, existing_comment_ids)
    task_history = History.objects.filter(task_fk=task)[:10]
    args['task'] = task
    args['comments'] = comments
    if user.is_superuser:
        args['staff_users'] = User.objects.filter(is_staff=True, is_active=True)
    args['history'] = task_history
    
    return render(request, 'view_task.html', args)

@login_required(login_url="/syslogin/login")
def create_task(request):
    args = {}
    
    args.update(get_auth_user(request))
    
    if args['user'].is_staff:
        customers = User.objects.filter(is_active=True,
                                        is_staff=False,
                                        is_superuser=False)
        products = Product.objects.all()
    else:
        customers = None
        products = Product.objects.filter(users=args['user'])
    
    args['customers'] = customers 
    args['products'] = products 

    if request.POST:
        # Данные из формы
        subject = request.POST.get('subject')
        prio = request.POST.get('prio')
        text = request.POST.get('text')
        product = request.POST.get('product')
        fileinput = request.FILES.getlist('file')

        if 'customer' in request.POST:
            task_customer = request.POST.get('customer')
            task_communication = request.POST.get('channel')
        else:
            task_customer = args['user'].id
            task_communication = 'WEB'
            

        try:
            data = {
                'id': None,
                'task_subject': subject,
                'task_prio': prio,
                'task_text': text,
                'task_customer_id': task_customer,
                'task_communication': task_communication,
                'task_product_id': product
            }

            new_task = create_update_task(data)           

            if fileinput:
                for attach in fileinput:
                    
                    new_file = TaskFiles(task_fk=new_task,
                                         task_file=attach)
                    new_file.save()

            
            history_content = {
                    'task_fk':new_task,
                    'user_fk': args['user'],
                    'history_text': 'Создал обращение'
                }

            add_history(**history_content)

            # Отправка сотрудникам
            task_url = request.build_absolute_uri(new_task.get_absolute_url())
            take_url = request.build_absolute_uri(new_task.get_absolute_url() + '/take')

            files_html = ''.join(
                '<li><a href="{}">{}</a></li>'.format(
                    request.build_absolute_uri(f.get_file_url()), f.get_filename()
                )
                for f in new_task.taskfiles_set.all()
            )

            html_msg = """
            <h2>Новое обращение #{id}</h2>
            <p><b>Тема:</b> {subject}</p>
            <p><b>Заказчик:</b> {customer}</p>
            <p><b>Приоритет:</b> {prio}</p>
            <p><b>КПО:</b> {product}</p>
            <p><b>Дата создания:</b> {date}</p>
            <p><b>Описание:</b></p>
            <div>{text}</div>
            {files_block}
            <hr>
            <p><a href="{task_url}">Открыть заявку</a></p>
            <p><a href="{take_url}">Взять задачу</a></p>
            """.format(
                id=new_task.id,
                subject=new_task.task_subject,
                customer=new_task.task_customer,
                prio=new_task.get_task_prio_display(),
                product=new_task.task_product or 'Не указан',
                date=new_task.task_createdate.strftime('%d.%m.%Y %H:%M'),
                text=new_task.task_text,
                files_block='<p><b>Вложения:</b></p><ul>{}</ul>'.format(files_html) if files_html else '',
                task_url=task_url,
                take_url=take_url,
            )

            mail_context = {
                'msg': 'Пользователь {} создал обращение #{}.'.format(args['user'], new_task.id),
                'html_msg': html_msg,
                'subject': subject,
                'recepients': [user.email if user.email is not None else '' for user in User.objects.filter(is_staff=True)]
            }

            send_email_notification(mail_context)

            # Отправка пользователю
            check_url = request.build_absolute_uri('/check') + '?' + urlencode({
                'uuid': new_task.task_uuid,
                'email': args['user'].email,
            })
            html_msg_customer = """
            <h3>Вы создали обращение #{id}</h3>
            <p><b>Тема:</b> {subject}</p>
            <p>Статус заявки можно посмотреть в личном кабинете, либо без входа в аккаунт — по ссылке ниже.</p>
            <hr>
            <p><a href="{check_url}">Проверить статус заявки</a></p>
            <p style="color:#6c757d; font-size:.85em;">UID заявки: {uuid}</p>
            """.format(
                id=new_task.id,
                subject=subject,
                check_url=check_url,
                uuid=new_task.task_uuid,
            )
            mail_context = {
                'msg': 'Вы создали обращение. Статус заявки можно посмотреть в ЛК или по ID: {0}\nПроверить статус: {1}'.format(
                    new_task.task_uuid, check_url),
                'html_msg': html_msg_customer,
                'subject': subject,
                'recepients': [args['user'].email]
            }
                   
            send_email_notification(mail_context)

            print(mail_context)

            messages.success(request, 'Заявка успешно отправлена!')
            return redirect(view_task, task_id=new_task.id)

        except Exception as error:
            args['error'] = 'Ошибка'
            # TODO логгирование
            print(error)

    return render(request, 'create_task.html', args)


@login_required(login_url="/syslogin/login")
def add_comment(request, task_id):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']
    task = Task.objects.get(id=task_id)

    if not user.is_staff and task.task_customer != user:
        raise Http404

    if request.POST:
        comment_text = request.POST.get('comment_text', '')
        has_question = request.POST.get('has_question', '')
        is_answer = request.POST.get('is_answer', '')
        reply_author = request.POST.get('reply_author', '')
        reply_text = request.POST.get('reply_text', '')
        reply_comment_id = request.POST.get('reply_comment_id', '')
        comment_files = request.FILES.getlist('comment_files')

        if reply_author and reply_text:
            quote = '<blockquote data-reply-id="{}" style="cursor:pointer;"><small class="reply-author">{}</small><div class="reply-body">{}</div></blockquote>'.format(
                reply_comment_id, reply_author, reply_text)
            comment_text = quote + comment_text

        comment_text = sanitize_rich_text(comment_text)

        try:
            new_comment = TaskComment(task_fk_id=task_id,
                                      comment_author=args['user'],
                                      comment_text=comment_text)
            new_comment.save()

            for f in comment_files:
                TaskCommentFile.objects.create(comment_fk=new_comment, comment_file=f)

            if has_question == 'on':
                task = Task.objects.filter(id = task_id).update(task_status = 'REQ')
            
            if is_answer == 'on':
                task = Task.objects.filter(id = task_id).update(task_status = 'ANS')


            
            history_content = {
                        'task_fk_id':task_id,
                        'user_fk': args['user'],
                        'history_text': 'Оставил комментарий'
                    }

            add_history(**history_content)

           # Отправка комментариев
            mail_context = {
                'msg': 'Пользователь {} оставил комментарий к задаче.\nКомментарий: {}'.format(
                    args['user'].get_full_name(),
                    comment_text),
                'subject': task.task_subject
            }

            if args['user'] == task.task_customer:
                if task.task_executor:
                    mail_context['recepients'] = [task.task_executor.email]
                else:
                    mail_context['recepients'] = [user.email if user.email is not None else '' for user in User.objects.filter(is_staff=True)]
            else:
                mail_context['recepients'] = [task.task_customer.email]

            send_email_notification(mail_context)

        except Exception as e:
            print(e)
            #pass
        
        # return redirect("/task/show/%d" % task_id)
        return redirect(view_task, task_id=task_id)


@login_required(login_url="/syslogin/login")
def take_task(request, task_id):
    args = {}
    args.update(get_auth_user(request))

    if not args['user'].is_staff:
        raise Http404

    start = datetime.now()

    Task.objects.filter(id=task_id).update(task_executor=args['user'],
                                           task_status='WORK',
                                           task_startdate=start)

    task = Task.objects.get(id=task_id)

    history_content = {
                    'task_fk_id':task_id,
                    'user_fk': args['user'],
                    'history_text': 'Взял задачу в работу'
                }

    add_history(**history_content)

    if task.task_customer and task.task_customer.email:
        task_url = request.build_absolute_uri(task.get_absolute_url())
        executor_name = args['user'].get_full_name() or str(args['user'])

        html_msg = """
        <h2>Ваше обращение принято в работу</h2>
        <p><b>Заявка:</b> #{id} — {subject}</p>
        <p><b>Исполнитель:</b> {executor}</p>
        <p><b>Дата принятия:</b> {date}</p>
        <hr>
        <p><a href="{task_url}">Открыть заявку</a></p>
        """.format(
            id=task.id,
            subject=task.task_subject,
            executor=executor_name,
            date=start.strftime('%d.%m.%Y %H:%M'),
            task_url=task_url,
        )

        mail_context = {
            'msg': 'Ваше обращение #{} принято в работу. Исполнитель: {}'.format(task.id, executor_name),
            'html_msg': html_msg,
            'subject': 'Обращение #{} принято в работу'.format(task.id),
            'recepients': [task.task_customer.email],
        }

        send_email_notification(mail_context)

    messages.success(request, 'Вы взяли заявку #{} в работу.'.format(task.id))
    return redirect(view_task, task_id=task_id)

@login_required(login_url="/syslogin/login")
def continue_task(request, task_id):
    if not request.user.is_staff:
        raise Http404
    task = Task.objects.get(id=task_id)
    old_status = task.task_status
    Task.objects.filter(id=task_id).update(task_status='WORK')
    task.refresh_from_db()
    if task.task_customer and task.task_customer.email:
        send_status_change_email(request, task, old_status, 'WORK', [task.task_customer.email])
    return redirect(view_task, task_id=task_id)
    

def edit_task(request, task_id):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    task = Task.objects.get(id=task_id)

    if task.task_customer != user:
        raise Http404

    args['task'] = task
      
    

    if request.POST:
        # Данные из формы
        subject = request.POST.get('subject')
        prio = request.POST.get('prio')
        text = request.POST.get('text')
        product = request.POST.get('product')
        fileinput = request.FILES.getlist('file')        

        try:
            data = {
                'id': task_id,
                'task_subject':subject,
                'task_prio':prio,
                'task_text':text,
                'task_product': product          
            }

            new_task = create_update_task(data)           

            if fileinput:
                for attach in fileinput:
                    
                    new_file = TaskFiles(task_fk=new_task,
                                         task_file=attach)
                    new_file.save()

            history_content = {
                    'task_fk_id':task_id,
                    'user_fk': args['user'],
                    'history_text': 'Отредактировал обращение'
                }

            add_history(**history_content)
                
            

        except Exception as e:
            print(e)

        return redirect(view_task, task_id=task_id)
    
    return render(request, 'create_task.html', args)


@login_required(login_url="/syslogin/login")
def attach_file(request, task_id):
    user = get_auth_user(request)['user']
    task = Task.objects.get(id=task_id)

    if not user.is_staff and task.task_customer != user:
        raise Http404

    if request.POST:
        fileinput = request.FILES.getlist('file')

        try:
            for attach in fileinput:
                    
                    file = TaskFiles(task_fk_id=task_id,
                                     task_file=attach)
                    file.save()
            
            history_content = {
                        'task_fk_id':task_id,
                        'user_fk': get_auth_user(request)['user'],
                        'history_text': 'Прикрепил файл'
                    }

            add_history(**history_content)

        except Exception as e:
            print(e)


        return redirect(view_task, task_id=task_id)

def delete_file(request, task_id, file_id):
    user = get_auth_user(request)['user']
    task = Task.objects.get(id=task_id)

    if task.task_customer != user:
        raise Http404

    task_file = TaskFiles.objects.get(id=file_id)
    task_file.delete()

    history_content = {
                        'task_fk_id':task_id,
                        'user_fk': get_auth_user(request)['user'],
                        'history_text': 'Удалил файл'
                    }

    add_history(**history_content)

    return redirect(view_task, task_id=task_id)

@login_required(login_url="/syslogin/login")
def end_task(request, task_id):
    if not request.user.is_staff:
        raise Http404
    now = datetime.now()
    task = Task.objects.get(id=task_id)
    old_status = task.task_status
    Task.objects.filter(id=task_id).update(task_status='END', task_fact_enddate=now)
    task.refresh_from_db()

    history_content = {
                        'task_fk_id':task_id,
                        'user_fk': get_auth_user(request)['user'],
                        'history_text': 'Завершил задачу'
                    }
    add_history(**history_content)

    if task.task_customer and task.task_customer.email:
        send_status_change_email(request, task, old_status, 'END', [task.task_customer.email])

    return redirect(view_task, task_id=task_id)

@login_required(login_url="/syslogin/login")
def close_task(request, task_id):
    if not request.user.is_superuser:
        raise Http404
    task = Task.objects.get(id=task_id)
    old_status = task.task_status
    Task.objects.filter(id=task_id).update(task_status='CLOSE')
    task.refresh_from_db()

    history_content = {
                        'task_fk_id':task_id,
                        'user_fk': get_auth_user(request)['user'],
                        'history_text': 'Закрыл задачу'
                    }
    add_history(**history_content)

    recipients = []
    if task.task_customer and task.task_customer.email:
        recipients.append(task.task_customer.email)
    if task.task_executor and task.task_executor.email:
        recipients.append(task.task_executor.email)
    send_status_change_email(request, task, old_status, 'CLOSE', recipients)

    return redirect(view_task, task_id=task_id)

@login_required(login_url="/syslogin/login")
def reopen_task(request, task_id):
    user = request.user
    task = Task.objects.get(id=task_id)

    is_own_ended_task = task.task_customer == user and task.task_status == 'END'
    if not user.is_superuser and not is_own_ended_task:
        raise Http404

    old_status = task.task_status
    Task.objects.filter(id=task_id).update(task_status='WORK')
    task.refresh_from_db()

    history_content = {
                        'task_fk_id':task_id,
                        'user_fk': get_auth_user(request)['user'],
                        'history_text': 'Заново открыл задачу'
                    }
    add_history(**history_content)

    recipients = [u.email for u in User.objects.filter(is_staff=True) if u.email]
    send_status_change_email(request, task, old_status, 'WORK', recipients)

    return redirect(view_task, task_id=task_id)

@csrf_exempt
@login_required(login_url="/syslogin/login")
def upload_editor_image(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        from django.core.files.storage import default_storage
        path = default_storage.save('editor_uploads/' + file.name, file)
        url = '/media/' + path
        return JsonResponse({'success': True, 'url': url})
    return JsonResponse({'error': 'no file'}, status=400)

@login_required(login_url="/syslogin/login")
def products_for_customer(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    customer_id = request.GET.get('customer_id', '')
    if customer_id.isdigit():
        products = list(Product.objects.filter(users__id=customer_id).values('id', 'product_name'))
    else:
        products = []
    return JsonResponse({'products': products})


def assign_executor(request, task_id):
    user = get_auth_user(request)['user']
    if not user.is_superuser:
        raise Http404
    if request.POST:
        executor_id = request.POST.get('executor_id', '')
        task = Task.objects.get(id=task_id)
        if executor_id:
            if task.task_executor_id and str(task.task_executor_id) != str(executor_id):
                messages.error(request, 'На заявке уже есть исполнитель. Сначала снимите его, затем назначьте нового.')
                return redirect(view_task, task_id=task_id)
            Task.objects.filter(id=task_id).update(
                task_executor_id=executor_id,
                task_status='WORK',
                task_startdate=datetime.now()
            )
            add_history(task_fk=task, user_fk=user, history_text='Назначил исполнителя')
            executor = User.objects.get(id=executor_id)
            messages.success(request, 'Исполнитель назначен: {}'.format(executor.get_full_name() or executor.username))

            if executor.email:
                task_url = request.build_absolute_uri(task.get_absolute_url())
                html_msg = """
                <h2>Вам поручено обращение</h2>
                <p><b>Заявка:</b> #{id} — {subject}</p>
                <p><b>Заказчик:</b> {customer}</p>
                <p><b>Приоритет:</b> {prio}</p>
                <hr>
                <p><a href="{task_url}">Открыть заявку</a></p>
                """.format(
                    id=task.id,
                    subject=task.task_subject,
                    customer=task.task_customer,
                    prio=task.get_task_prio_display(),
                    task_url=task_url,
                )
                mail_context = {
                    'msg': 'Вам поручено обращение #{} — {}.'.format(task.id, task.task_subject),
                    'html_msg': html_msg,
                    'subject': 'Вам назначено обращение #{}'.format(task.id),
                    'recepients': [executor.email],
                }
                send_email_notification(mail_context)
        else:
            add_history(task_fk=task, user_fk=user, history_text='Снял исполнителя')
            Task.objects.filter(id=task_id).update(task_executor=None)
            messages.success(request, 'Исполнитель снят с заявки.')
    return redirect(view_task, task_id=task_id)

def delete_comment(request, task_id, comment_id):
    user = get_auth_user(request)['user']
    comment = TaskComment.objects.get(id=comment_id)
    if comment.comment_author == user:
        comment.delete()
    return redirect(view_task, task_id=task_id)

def edit_comment(request, task_id, comment_id):
    user = get_auth_user(request)['user']
    comment = TaskComment.objects.get(id=comment_id)
    if comment.comment_author == user and request.POST:
        new_text = request.POST.get('comment_text', '').strip()
        blockquote = request.POST.get('reply_blockquote', '')
        if new_text:
            comment.comment_text = sanitize_rich_text(blockquote + new_text)
            comment.save()

        if request.POST.get('delete_legacy_file') == 'on' and comment.comment_file:
            comment.comment_file.delete(save=False)
            comment.comment_file = None
            comment.save()

        delete_file_ids = request.POST.getlist('delete_file_ids')
        if delete_file_ids:
            TaskCommentFile.objects.filter(id__in=delete_file_ids, comment_fk=comment).delete()

        for f in request.FILES.getlist('comment_files'):
            TaskCommentFile.objects.create(comment_fk=comment, comment_file=f)

    from django.urls import reverse
    return redirect(reverse('view_task', args=[task_id]) + '#comment-' + str(comment_id))

def accept_decision(request, task_id, comment_id):
    comment = TaskComment.objects.filter(comment_isresult=True)

    if comment.exists:
        comment.update(comment_isresult=False)    
    
    set_decision = TaskComment.objects.filter(id=comment_id).update(comment_isresult=True)

    history_content = {
                        'task_fk_id':task_id,
                        'user_fk': get_auth_user(request)['user'],
                        'history_text': 'Отметил комментарий как решение'
                    }

    add_history(**history_content)

    return redirect(view_task, task_id=task_id)
