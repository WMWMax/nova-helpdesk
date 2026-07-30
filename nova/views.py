from django.shortcuts import render, HttpResponse, redirect, Http404
from django.core.mail import send_mail, EmailMultiAlternatives
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from tasks.models import Task, Solution
from products.models import Product
from history.models import History
from .settings import EMAIL_HOST_USER

import xlsxwriter
from io import StringIO, BytesIO

def index(request):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']
    if user.is_active:
        if user.is_staff:
        # return redirect(admin_dashboard(request, user.id))
            return redirect("/admins/%d" % user.id)
        else:
        # return redirect(user_dashboard(request, user.id))
            return redirect("/users/%d" % user.id)
    else:
        return redirect("/syslogin/login")


@login_required(login_url="/syslogin/login")
@never_cache
def user_dashboard(request, user_id):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']
    args['products'] = user.products.all()

    all_tasks = Task.objects.filter(task_customer=user)
    paginator = Paginator(all_tasks, 10)
    args['tasks'] = paginator.get_page(request.GET.get('page', 1))
    args['get_params'] = ''

    stat = get_base_user_statistic(user)
    args['stat'] = stat

    return render(request, 'users/dashboard.html', args)


@login_required(login_url="/syslogin/login")
@never_cache
def admin_dashboard(request, user_id):
    args = {}
    args.update(get_auth_user(request))
    user = args['user']

    if user.is_superuser:
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.exclude(task_status='CLOSE')

    status_filter = request.GET.get('status', '')
    prio_filter = request.GET.get('prio', '')
    search_filter = request.GET.get('search', '')

    if status_filter:
        tasks = tasks.filter(task_status=status_filter)
    if prio_filter:
        tasks = tasks.filter(task_prio=prio_filter)
    if search_filter:
        tasks = tasks.filter(task_subject__icontains=search_filter)

    get_params = request.GET.copy()
    get_params.pop('page', None)
    paginator = Paginator(tasks, 20)
    args['tasks'] = paginator.get_page(request.GET.get('page', 1))
    args['get_params'] = get_params.urlencode()
    args['status_filter'] = status_filter
    args['prio_filter'] = prio_filter
    args['search_filter'] = search_filter

    # Заявки, назначенные этому сотруднику за последние 3 дня
    three_days_ago = datetime.now() - timedelta(days=3)
    args['newly_assigned'] = Task.objects.filter(
        task_executor=user,
        task_startdate__gte=three_days_ago,
        task_status='WORK'
    ).order_by('-task_startdate')[:5]

    return render(request, 'admins/dashboard.html', args)


def get_auth_user(request):
    args = {}
    user = auth.get_user(request)
    args['user'] = user
    return args


def get_base_staff_statistic(user):
    now = datetime.today()

    labels = []
    created_items = []
    closed_items = []
    for day in range(6, -1, -1):
        date = now - timedelta(day)
        if user.is_superuser:
            created_task = Task.objects.filter(task_createdate__day=date.day).count()
            closed_task = Task.objects.filter(task_fact_enddate__day=date.day).count()
        else:    
            created_task = Task.objects.filter(task_createdate__day=date.day, task_executor=user).count()
            closed_task = Task.objects.filter(task_fact_enddate__day=date.day, 
                                              task_executor=user, 
                                              task_status='CLOSE').count()
        labels.append(date.strftime("%d %B"))
        created_items.append(created_task) 
        closed_items.append(closed_task) 
        
    data = {'labels': labels,
            'created_items': created_items,
            'closed_items': closed_items}
    
    return data

def get_base_user_statistic(user):

    now = datetime.today()

    labels = ['Критический', 'Высокий', 'Низкий']
   
    crit_count = Task.objects.filter(task_customer=user, task_prio='CRIT').exclude(task_status='CLOSE') \
                                                                          .exclude(task_status='END') \
                                                                          .count()
 
    high_count = Task.objects.filter(task_customer=user, task_prio='HIGH').exclude(task_status='CLOSE') \
                                                                          .exclude(task_status='END') \
                                                                          .count()
     
    low_count = Task.objects.filter(task_customer=user, task_prio='LOW').exclude(task_status='CLOSE') \
                                                                         .exclude(task_status='END') \
                                                                         .count()
    
    in_progress = Task.objects.filter(task_customer=user).exclude(task_status='NEW').exclude(task_status='CLOSE').exclude(task_status='END').count()
    new_tasks = Task.objects.filter(task_customer=user,task_status='NEW').count()


    data = {'labels': labels, 'counts': [crit_count, high_count , low_count], 'count_status':[in_progress, new_tasks]}

    return data

def check_my_task(request):
    args = {}
    uuid = request.POST.get('uuid') or request.GET.get('uuid', '')
    email = request.POST.get('email') or request.GET.get('email', '')

    # Обычная отправка формы (POST) или переход по ссылке из письма
    # со уже подставленными UID и email (GET)
    if request.method == 'POST' or (uuid and email):
        try:
            user = User.objects.get(email=email)
            task = Task.objects.get(task_uuid=uuid, task_customer=user)

            args['task'] = task
            args['history'] = History.objects.filter(task_fk=task)

        except Exception as e:
 #           print(e)
            pass
        return render(request, 'check_task.html', args)

    else:
        raise Http404


def send_email_notification(context):
    subj, from_mail = context['subject'], EMAIL_HOST_USER
    text_content = context['msg']
    html_content = context.get('html_msg')

    try:
        if html_content:
            msg = EmailMultiAlternatives(subj, text_content, from_mail, context['recepients'])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
        else:
            send_mail(subj, text_content, from_mail, context['recepients'])
    except Exception as e:
        # Сбой почтового сервера не должен ломать основное действие
        # (назначение исполнителя, смену статуса и т.д.)
        print('Ошибка отправки письма:', e)

def dump_report_to_excel(requests):
    end = datetime.today()
    start = end - timedelta(days=90)
    user = get_auth_user(requests)['user']

    tasks = Task.objects.filter(task_customer=user, task_createdate__gt = start) 

    output = BytesIO()    

    workbook = xlsxwriter.Workbook(output, {'remove_timezone': True})
    worksheet = workbook.add_worksheet('Report')

    worksheet.write('A1', 'Номер заявки')
    worksheet.write('B1', 'Приоритет')
    worksheet.write('C1', 'Статус')
    worksheet.write('D1', 'Сведение о КПО')
    worksheet.write('E1', 'Дата поступления')
    worksheet.write('F1','Дата закрытия')
    worksheet.write('G1', 'Время исполнения')

    col = 0
    for row, task in enumerate(tasks, start=1):
        if task.task_fact_enddate is not None:
            fact = task.task_fact_enddate.strftime('%Y-%m-%m %H:%M')
        else:
            fact = ''
        worksheet.write(row, col, task.id)
        worksheet.write(row, col+1, task.get_task_prio_display())
        worksheet.write(row, col+2, task.get_task_status_display())
        worksheet.write(row, col+3, str(task.task_product))
        worksheet.write(row, col+4, task.task_createdate.strftime('%Y-%m-%m %H:%M'))
        worksheet.write(row, col+5, fact)
        worksheet.write(row, col+6, 'время исполнения')
        

    workbook.close()

    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename=report.xlsx'

    output.close()

    return response

@login_required(login_url="/syslogin/login")
def help_view(request):
    args = {}
    args.update(get_auth_user(request))
    return render(request, 'help.html', args)


@login_required(login_url="/syslogin/login")
def database_view(request):
    if not request.user.is_staff:
        raise Http404

    args = {}
    args.update(get_auth_user(request))
    args['customers'] = User.objects.filter(is_staff=False, is_active=True).order_by('last_name')
    args['products'] = Product.objects.prefetch_related('users').all().order_by('product_name')
    args['solutions'] = Solution.objects.select_related('solution_product').all().order_by('solution_title')

    return render(request, 'database.html', args)


@login_required(login_url="/syslogin/login")
def analytics_view(request):
    if not request.user.is_staff:
        raise Http404

    args = {}
    args.update(get_auth_user(request))

    all_tasks = Task.objects.all()
    total = all_tasks.count()

    by_status = {
        'Новый':        all_tasks.filter(task_status='NEW').count(),
        'В работе':     all_tasks.filter(task_status='WORK').count(),
        'Запрос':       all_tasks.filter(task_status='REQ').count(),
        'Уточнен':      all_tasks.filter(task_status='ANS').count(),
        'Предоставлен': all_tasks.filter(task_status='END').count(),
        'Закрыт':       all_tasks.filter(task_status='CLOSE').count(),
        'Отклонен':     all_tasks.filter(task_status='REF').count(),
    }

    by_prio = {
        'Критический': all_tasks.filter(task_prio='CRIT').count(),
        'Высокий':     all_tasks.filter(task_prio='HIGH').count(),
        'Низкий':      all_tasks.filter(task_prio='LOW').count(),
    }

    by_product = (
        all_tasks.exclude(task_product=None)
                 .values('task_product__product_name')
                 .annotate(count=Count('id'))
                 .order_by('-count')
    )

    taken_tasks = all_tasks.exclude(task_startdate=None)
    avg_response = None
    if taken_tasks.exists():
        durations = []
        for t in taken_tasks:
            delta = t.task_startdate - t.task_createdate
            durations.append(delta.total_seconds() / 3600)
        avg_hours = sum(durations) / len(durations)
        if avg_hours < 24:
            avg_response = '{:.1f} ч'.format(avg_hours)
        else:
            avg_response = '{:.1f} дн'.format(avg_hours / 24)

    stat = get_base_staff_statistic(request.user)

    args['total'] = total
    args['count_new'] = by_status['Новый']
    args['count_work'] = by_status['В работе']
    args['by_status'] = by_status
    args['by_prio'] = by_prio
    args['prio_crit'] = by_prio['Критический']
    args['prio_high'] = by_prio['Высокий']
    args['prio_low'] = by_prio['Низкий']
    args['by_product'] = by_product
    args['avg_response'] = avg_response
    args['stat'] = stat

    return render(request, 'analytics.html', args)


def handler_404(request, exception):
    return HttpResponse('<h1>Page not Found</h1>')
