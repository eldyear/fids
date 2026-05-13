# flights/views.py
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.utils import IntegrityError
from django.db.models import Q, F, Sum, ExpressionWrapper, fields
from .forms import FlightFilterForm, ServiceForm, LogFilterForm
from .models import Flight, Service, Airport, ServiceType, ServicePrice, UserProfile, TechCard, LogEntry, Firm, Airline
from .api_importer import import_flights_from_api, import_service_types_from_api
from .services_to_techcard import generate_tech_card_from_services
from datetime import datetime, date, timedelta, time
import logging
from django import template
from django.template.defaulttags import register
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
import json
from .templatetags.flights_extras import get_item
from django.template.loader import get_template, render_to_string
from django.conf import settings
import os
from django.contrib.staticfiles import finders
from xhtml2pdf import pisa
from openpyxl import Workbook
import io
import csv
from .link_flights import link_arrival_departure_flights
from django.views.decorators.csrf import csrf_exempt, requires_csrf_token
from django.contrib.auth.decorators import login_required, user_passes_test
from urllib.parse import unquote
from .utils import log_action
import pytz
from functools import wraps
from django.utils.safestring import mark_safe
# import time
# from mobiledetect.middleware import DetectMiddleware  # Not installed

logger = logging.getLogger(__name__)

@register.filter(name='add_class')
def add_class(value, arg):
    return value.as_widget(attrs={'class': arg})

def login_required_mobile(view_func):
    """
    Декоратор, который перенаправляет неавторизованных пользователей
    на мобильную или десктопную страницу авторизации.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        login_url = settings.LOGIN_URL
        if request.is_mobile:
            return redirect('login_mobile') # Перенаправляем на мобильную версию
        else:
            return redirect(f'{login_url}?next={request.path}')

    return _wrapped_view

def home(request):
    """
    Представление, которое определяет, куда перенаправить пользователя
    в зависимости от его устройства (мобильный или десктоп).
    """
    # return HttpResponse(f"Is mobile: {request.device.get('is_mobile', 'Not found')}<br>"
    #                     f"Device type: {request.device.get('type', 'Not found')}<br>"
    #                     f"Full device dict: {request.device}")
    if request.user.is_authenticated:
        # Безопасно проверяем наличие request.device и ключа is_mobile
        is_mobile = getattr(request, 'device', {}).get('is_mobile', False)
        if is_mobile:
            return redirect('supervisor_dashboard_mobile')
        else:
            return redirect('supervisor_dashboard')
    else:
        # Если пользователь не авторизован, отправляем его на соответствующую страницу входа
        is_mobile = getattr(request, 'device', {}).get('is_mobile', False)
        if is_mobile:
            return redirect('login_mobile')
        else:
            return redirect('login')

@login_required
def supervisor_dashboard(request):
    """
    Главная страница для супервайзера.
    Теперь поддерживает два режима: 'flights' и 'techcards'.
    """

    view_mode = request.GET.get('view', 'flights')

    if request.method == 'POST':
        filter_date_str = request.POST.get('date')
        filter_date_for_api = filter_date_str if filter_date_str else date.today().strftime('%Y-%m-%d')

        messages.info(request, "Начинается процесс импорта рейсов...")

        try:
            # Вызываем только одну функцию, которая и импортирует, и связывает
            success, message = import_flights_from_api(filter_date_for_api)
            if success:
                # Используем сообщение, возвращенное функцией импорта
                messages.success(request, message)
            else:
                messages.error(request, f"Ошибка при импорте рейсов: {message}")
        except Exception as e:
            messages.error(request, f"Произошла непредвиденная ошибка: {e}")

        url_params = f"date={filter_date_for_api}&view={view_mode}"
        return redirect(f"{request.path}?{url_params}")

    else:
        # Get the date from the request, or default to today's date
        initial_date = request.GET.get('date', date.today())

        # If the date is a date object, convert it to a string in 'YYYY-MM-DD' format
        if isinstance(initial_date, date):
            initial_date = initial_date.strftime('%Y-%m-%d')

        initial_data = {
            'date': initial_date,
        }
        form = FlightFilterForm(request.GET or initial_data)

        flights_with_info = []
        tech_cards = []

        if form.is_valid():
            filter_date = form.cleaned_data.get('date')

            is_admin = request.user.is_superuser
            today = date.today()
            create_limit_date = today - timedelta(days=2)

            if view_mode == 'flights':
                # ИСПРАВЛЕННЫЙ ЗАПРОС: Фильтруем по дате, затем применяем остальные условия
                filtered_flights = Flight.objects.filter(
                    Q(is_active=True), # Добавляем фильтр по активности рейса
                    Q(date=filter_date),
                    Q(board_base='B') | (
                        Q(direction='P') &
                        ~Q(actual_time__isnull=True) &
                        ~Q(actual_time__exact='')
                    )
                ).order_by(F('actual_time').desc())

                for flight in filtered_flights:
                    # --- ДОБАВЛЕНА КОНВЕРТАЦИЯ FACTDATE ---
                    # Проверяем, существует ли фактическая дата в строковом формате
                    if flight.date_fact:
                        # Создаем новый атрибут, который будет содержать объект даты
                        flight.date_fact_obj = datetime.strptime(flight.date_fact, '%Y-%m-%d').date()
                    else:
                        flight.date_fact_obj = None
                    # --- КОНЕЦ ДОБАВЛЕННОЙ КОНВЕРТАЦИИ ---

                    # Упрощенная логика: получаем все техкарты и проверяем наличие техкарты пользователя
                    all_tech_cards = TechCard.objects.filter(flight=flight).order_by('id')
                    user_tech_card_exists = all_tech_cards.filter(author=request.user).exists()
                    can_create = is_admin or (flight.date >= create_limit_date)

                    flights_with_info.append({
                        'flight': flight,
                        'all_tech_cards': all_tech_cards,
                        'user_tech_card_exists': user_tech_card_exists,
                        'can_create_tech_card': can_create,
                    })

            elif view_mode == 'techcards':
                tech_cards = TechCard.objects.filter(
                    flight__date=filter_date,
                    author=request.user,
                ).order_by('-created_at')

        context = {
            'form': form,
            'flights_with_info': flights_with_info,
            'tech_cards': tech_cards,
            'view_mode': view_mode,
        }
        return render(request, 'flights/supervisor_dashboard.html', context)

@login_required
@require_POST
def import_services_view(request):
    """
    Представление для ручного запуска импорта типов услуг из API.
    """
    success, message = import_service_types_from_api()
    if success:
        messages.success(request, message)
    else:
        messages.error(request, f"Ошибка при импорте услуг: {message}")
    
    return redirect('supervisor_dashboard')

@login_required
def supervisor_dashboard_mobile(request):
    form = FlightFilterForm(request.GET)
    view_mode = request.GET.get('view', 'flights')
    flights_with_info = []
    tech_cards_list = []

    # Получаем общее количество типов услуг для прогресс-бара
    total_service_types = ServiceType.objects.count()

    if form.is_valid():
        selected_date = form.cleaned_data['date']
        two_days_ago = date.today() - timedelta(days=2)

        if view_mode == 'flights':
            flights = Flight.objects.filter(date=selected_date).order_by('time')
            flights = flights.select_related('dep_airport', 'arr_airport')

            for flight in flights:
                user_tech_card = TechCard.objects.filter(flight=flight, author=request.user).first()
                flight_info = {
                    'flight': flight,
                    'user_tech_card': user_tech_card,
                    'can_create_tech_card': flight.date >= two_days_ago,
                    'other_tech_cards': TechCard.objects.filter(flight=flight).exclude(author=request.user)
                }
                flights_with_info.append(flight_info)

        elif view_mode == 'techcards':
            tech_cards_list = TechCard.objects.filter(
                author=request.user,
                flight__date=selected_date
            ).select_related('author', 'flight__dep_airport', 'flight__arr_airport').prefetch_related('services__service_type').order_by('-created_at')

    context = {
        'form': form,
        'view_mode': view_mode,
        'flights_with_info': flights_with_info,
        'tech_cards': tech_cards_list,
        'total_service_types': total_service_types,
    }
    return render(request, 'flights/supervisor_dashboard_mobile.html', context)

# --- Остальные функции (manage_services_for_flight, delete_service, и т.д.) без изменений ---

def get_flights_for_linking(request):
    try:
        date_filter = request.GET.get('date_filter', 'today')
        airline_filter = request.GET.get('airline_filter', '')
        current_flight_id = request.GET.get('current_flight_id')

        target_date = date.today()
        if date_filter == 'yesterday':
            target_date -= timedelta(days=1)
        elif date_filter == 'tomorrow':
            target_date += timedelta(days=1)

        flights_queryset = Flight.objects.filter(date=target_date)

        if current_flight_id:
            flights_queryset = flights_queryset.exclude(pk=current_flight_id)

        if airline_filter:
            flights_queryset = flights_queryset.filter(airline__code__iexact=airline_filter)

        flights_list = []
        for flight in flights_queryset:
            # ИСПРАВЛЕННАЯ СТРОКА:
            # Сначала проверяем, что объект не None, затем проверяем его тип
            actual_time_str = flight.actual_time.strftime('%H:%M') if flight.actual_time and isinstance(flight.actual_time, time) else '-'

            flights_list.append({
                'id': flight.id,
                'flight_num': flight.flight_num or '-',
                'direction': 'Прилет' if flight.direction == 'P' else 'Вылет',
                'airline_code': flight.airline.code if flight.airline else '-',
                'actual_time': actual_time_str
            })

        return JsonResponse({'flights': flights_list})

    except Exception as e:
        print(f"Ошибка в представлении get_flights_for_linking: {e}")
        return JsonResponse({'status': 'error', 'message': f"Произошла ошибка на сервере: {e}"}, status=500)

@require_POST
def update_flight_field(request):
    try:
        flight_id = request.POST.get('flight_id')
        field_name = request.POST.get('field_name')
        value = request.POST.get('value')

        flight = Flight.objects.get(pk=flight_id)

        if field_name == 'linked_flight':
            # Обрабатываем пустое значение для отмены связи
            linked_flight = None
            if value and value != 'None':
                linked_flight = Flight.objects.get(pk=value)
            flight.linked_flight = linked_flight
        else:
            setattr(flight, field_name, value)

        flight.save()

        # Логирование
        log_action(user=request.user, action='UPDATED', obj=flight, changes={field_name: value})

        return JsonResponse({'status': 'success', 'message': f'Поле {field_name} успешно обновлено.'})
    except Exception as e:
        print(f"Ошибка при обновлении поля рейса: {e}")
        return JsonResponse({'status': 'error', 'message': f'Ошибка при сохранении: {e}'}, status=500)

@login_required
def manage_services_for_flight(request, flight_id, tech_card_id=None):
    logger.info(f"--- manage_services_for_flight started for flight_id: {flight_id}, tech_card_id: {tech_card_id} ---")
    flight = get_object_or_404(Flight, pk=flight_id)

    # --- ДОБАВЛЕНА КОНВЕРТАЦИЯ FACTDATE ДЛЯ ТЕКУЩЕГО РЕЙСА ---
    if flight.date_fact:
        try:
            flight.date_fact_obj = datetime.strptime(flight.date_fact, '%Y-%m-%d').date()
        except ValueError:
            flight.date_fact_obj = None
    else:
        flight.date_fact_obj = None

    # --- КОНВЕРТАЦИЯ ДАТЫ ДЛЯ СВЯЗАННОГО РЕЙСА ---
    if flight.linked_flight:
        if flight.linked_flight.date_fact:
            try:
                flight.linked_flight.date_fact_obj = datetime.strptime(flight.linked_flight.date_fact, '%Y-%m-%d').date()
            except ValueError:
                flight.linked_flight.date_fact_obj = None
        else:
            flight.linked_flight.date_fact_obj = None
    # --- КОНЕЦ ДОБАВЛЕННОЙ КОНВЕРТАЦИИ ---

    current_user_name = f"{request.user.first_name} {request.user.last_name}"
    logger.debug("Querying supervisors, firms, airlines")
    supervisors = User.objects.filter(groups__name='supervisor').order_by('username')
    firms = Firm.objects.all().order_by('name')
    is_supervisor = request.user.groups.filter(name='supervisor').exists()
    airlines = Airline.objects.all().order_by('code')
    logger.debug("Queries completed")

    tech_card = None
    if tech_card_id:
        tech_card = get_object_or_404(TechCard, pk=tech_card_id, flight=flight)
    else:
        tech_card, created = TechCard.objects.get_or_create(
            flight=flight,
            author=request.user,
        )

    read_only = False
    if tech_card:
        if (tech_card.is_closed and tech_card.author != request.user) or \
           (tech_card.author != request.user and not is_supervisor):
            read_only = True

    services = tech_card.services.all().order_by('id') if tech_card else Service.objects.none()

    if request.method == 'POST' and not read_only:
        service_id = request.POST.get('service_id')

        # If a tech card doesn't exist, create one
        if not tech_card:
            try:
                with transaction.atomic():
                    tech_card = TechCard.objects.create(
                        flight=flight,
                        author=request.user,
                    )
            except IntegrityError:
                messages.error(request, 'Ошибка при создании техкарты. Попробуйте снова.')
                return redirect('manage_services_for_flight', flight_id=flight.id)

        if service_id:
            service = get_object_or_404(Service, pk=service_id, tech_card=tech_card)
            old_values = {
                'service_type': service.service_type_id,
                'description': service.description,
                'quantity': service.quantity,
                'unit_of_measure': service.unit_of_measure,
                'start_time': service.start_time,
                'end_time': service.end_time,
            }
            form = ServiceForm(request.POST, instance=service)
            action = 'UPDATED'
        else:
            form = ServiceForm(request.POST)
            action = 'CREATED'

        if form.is_valid():
            new_service = form.save(commit=False)
            new_service.tech_card = tech_card
            new_service.author = request.user

            # --- ИСПРАВЛЕННЫЙ КОД ДЛЯ ОБРАБОТКИ DURATION_FIELD ---
            service_type_obj = new_service.service_type

            if service_type_obj.category == 'time':
                duration_hours = int(request.POST.get('duration_hours', 0) or 0)
                duration_minutes = int(request.POST.get('duration_minutes', 0) or 0)

                new_service.duration_field = timedelta(hours=duration_hours, minutes=duration_minutes)

                new_service.quantity = None
                new_service.unit_of_measure = ''
                new_service.adults_count = None
                new_service.children_count = None
                new_service.infants_count = None

            elif service_type_obj.category == 'pass':
                new_service.duration_field = None
                new_service.quantity = None
                new_service.unit_of_measure = ''

            elif service_type_obj.category == 'int':
                new_service.duration_field = None
                new_service.adults_count = None
                new_service.children_count = None
                new_service.infants_count = None
            # --- КОНЕЦ ИСПРАВЛЕННОГО КОДА ---

            utc_timezone = pytz.timezone('UTC')
            if new_service.start_time:
                combined_datetime = datetime.combine(flight.date, new_service.start_time)
                new_service.start_time = utc_timezone.localize(combined_datetime).time()
            if new_service.end_time:
                 combined_datetime = datetime.combine(flight.date, new_service.end_time)
                 new_service.end_time = utc_timezone.localize(combined_datetime).time()

            new_service.save()

            # Log the action (if needed)
            if action == 'CREATED':
                log_message = f"Услуга '{new_service.service_type.name}' создана."
                log_details = {}
            elif action == 'UPDATED':
                log_message = f"Услуга '{new_service.service_type.name}' обновлена."
                log_details = {}
            log_action(user=request.user, action=action, instance=tech_card, changes={'message': log_message, 'details': log_details})

            tech_card.tech_card_text = generate_tech_card_from_services(tech_card)
            tech_card.save()

            messages.success(request, f"Услуга '{new_service.service_type.name}' успешно сохранена!")
            return redirect('view_services', flight_id=flight.id, tech_card_id=tech_card.id)

        else:
            messages.error(request, "Ошибка при сохранении услуги. Пожалуйста, проверьте данные.")

    # Handle GET requests and invalid POST requests
    form = ServiceForm(initial={'tech_card': tech_card.id} if tech_card else {})

    context = {
        'flight': flight,
        'services': services,
        'tech_card': tech_card,
        'form': form,
        'current_user_name': current_user_name,
        'read_only': read_only,
        'is_supervisor': is_supervisor,
        'users_for_fueler': supervisors,
        'airlines': airlines,
        'firms': firms,
        'tech_card_id': tech_card.id if tech_card else 0,
    }
    return render(request, 'flights/manage_services.html', context)

@login_required
@require_POST
def close_techcard(request, tech_card_id):
    """
    Закрывает техкарту и сохраняет информацию о пользователе, который её закрыл.
    """
    is_supervisor = request.user.groups.filter(name='supervisor').exists()

    try:
        tech_card = get_object_or_404(TechCard, id=tech_card_id)

        # Разрешаем закрывать техкарту только супервайзерам, и только если она ещё не закрыта.
        if not is_supervisor or tech_card.is_closed:
            return JsonResponse({'status': 'error', 'message': 'У вас нет прав для выполнения этого действия.'}, status=403)

        # Обновляем статус и записываем, кто закрыл техкарту
        tech_card.is_closed = True
        tech_card.closed_by = request.user
        tech_card.save()

        # Логируем действие
        log_action(
            user=request.user,
            action='UPDATED',
            instance=tech_card,
            changes={
                'message': 'Техкарта закрыта.',
                'details': {
                    'is_closed': {'old': False, 'new': True},
                    'closed_by': {'new': str(request.user.get_full_name())}
                }
            }
        )

        return JsonResponse({'status': 'success', 'message': 'Техкарта успешно закрыта.'})

    except TechCard.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Техкарта не найдена.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Ошибка: {e}'}, status=500)

@login_required
def manage_services_mobile(request, flight_id, tech_card_id=None):
    flight = get_object_or_404(Flight, pk=flight_id)
    is_supervisor = request.user.groups.filter(name='supervisor').exists()
    service_types = ServiceType.objects.all().order_by('name')

    tech_card = None
    if tech_card_id:
        tech_card = get_object_or_404(TechCard, pk=tech_card_id, flight=flight)

    read_only = False
    if tech_card:
        if tech_card.is_closed:
            read_only = True
        elif tech_card.author != request.user and not is_supervisor:
            read_only = True

    services = tech_card.services.all().order_by('id') if tech_card else Service.objects.none()

    if request.method == 'POST' and not read_only:
        service_id = request.POST.get('service_id')

        with transaction.atomic():
            if not tech_card:
                # Создаем техкарту только при сохранении первой услуги
                tech_card = TechCard.objects.create(flight=flight, author=request.user)
                messages.success(request, 'Создана новая техкарта.')

            if service_id:
                service = get_object_or_404(Service, pk=service_id, tech_card=tech_card)
                form = ServiceForm(request.POST, instance=service)
            else:
                form = ServiceForm(request.POST)

            if form.is_valid():
                new_service = form.save(commit=False)
                new_service.tech_card = tech_card
                new_service.author = request.user

                service_type_obj = new_service.service_type
                if service_type_obj.category == 'time':
                    duration_hours = int(request.POST.get('duration_hours', 0) or 0)
                    duration_minutes = int(request.POST.get('duration_minutes', 0) or 0)
                    new_service.duration_field = timedelta(hours=duration_hours, minutes=duration_minutes)
                    new_service.quantity = None
                    new_service.unit_of_measure = ''
                    new_service.adults_count = None
                    new_service.children_count = None
                    new_service.infants_count = None
                elif service_type_obj.category == 'pass':
                    new_service.duration_field = None
                    new_service.quantity = None
                    new_service.unit_of_measure = ''
                elif service_type_obj.category == 'int':
                    new_service.duration_field = None
                    new_service.adults_count = None
                    new_service.children_count = None
                    new_service.infants_count = None

                utc_timezone = pytz.timezone('UTC')
                if new_service.start_time:
                    combined_datetime = datetime.combine(flight.date, new_service.start_time)
                    new_service.start_time = utc_timezone.localize(combined_datetime).time()
                if new_service.end_time:
                     combined_datetime = datetime.combine(flight.date, new_service.end_time)
                     new_service.end_time = utc_timezone.localize(combined_datetime).time()

                new_service.save()

                tech_card.tech_card_text = generate_tech_card_from_services(tech_card)
                tech_card.save()

                messages.success(request, f"Услуга '{new_service.service_type.name}' успешно сохранена!")
                return redirect('manage_services_mobile', flight_id=flight.id, tech_card_id=tech_card.id)

            else:
                messages.error(request, mark_safe("Ошибка при сохранении услуги. Пожалуйста, проверьте данные. <ul>" + "".join(
                    [f"<li>{key}: {value[0]}</li>" for key, value in form.errors.items()]
                ) + "</ul>"))

    form = ServiceForm(initial={'tech_card': tech_card.id if tech_card else ''})

    context = {
        'flight': flight,
        'services': services,
        'tech_card': tech_card,
        'form': form,
        'read_only': read_only,
        'tech_card_id': tech_card.id if tech_card else '',
        'service_types': service_types,
    }
    return render(request, 'flights/manage_services_mobile.html', context)

@login_required
def delete_service(request, service_id):
    service = get_object_or_404(Service, pk=service_id)
    tech_card = service.tech_card
    flight = tech_card.flight
    if request.method == 'POST':
        service.delete()
        # Проверяем, остались ли услуги в техкарте. Если нет, удаляем техкарту
        if not tech_card.services.exists():
            tech_card.delete()
            messages.success(request, "Последняя услуга удалена. Техкарта была удалена.")
            return redirect('supervisor_dashboard') # Перенаправляем на главную
        else:
            tech_card.tech_card_text = generate_tech_card_from_services(tech_card)
            tech_card.save()
            messages.success(request, "Услуга успешно удалена.")
    return redirect('manage_services', flight_id=flight.id)

@login_required_mobile
def delete_service_mobile(request, service_id):
    if request.method == 'POST':
        service = get_object_or_404(Service, pk=service_id)
        flight_id = service.tech_card.flight.id
        tech_card_id = service.tech_card.id
        service.delete()
        messages.success(request, 'Услуга успешно удалена.')
    return redirect('manage_services_mobile_tc', flight_id=flight_id, tech_card_id=tech_card_id)

@login_required
def price_management(request):
    """
    Отображает страницу для управления ценами на услуги.
    """
    service_types = ServiceType.objects.all().order_by('name')
    prices = {sp.service_type_id: sp.price_per_unit for sp in ServicePrice.objects.all()}

    context = {
        'service_types': service_types,
        'prices': prices,
    }
    return render(request, 'flights/price_management.html', context)

@require_POST
def save_price(request):
    """
    Сохраняет цену для типа услуги через AJAX-запрос.
    """
    try:
        data = json.loads(request.body)
        service_type_id = data.get('service_type_id')
        price_per_unit = data.get('price_per_unit')

        service_type = get_object_or_404(ServiceType, pk=service_type_id)

        ServicePrice.objects.update_or_create(
            service_type=service_type,
            defaults={'price_per_unit': price_per_unit}
        )

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def finance_dashboard(request):
    """
    Главная страница для финансиста.
    Отображает готовые техкарты со всех рейсов с рассчитанной стоимостью.
    """
    initial_data = {
        'date': request.GET.get('date', date.today()),
        'direction': request.GET.get('direction', ''),
        'region': request.GET.get('region', ''),
    }
    form = FlightFilterForm(request.GET or initial_data)
    tech_cards_with_costs = []

    if form.is_valid():
        filter_date = form.cleaned_data.get('date')
        filter_direction = form.cleaned_data.get('direction')
        filter_region = form.cleaned_data.get('region')

        # Начинаем с полного списка техкарт
        tech_cards_queryset = TechCard.objects.all()

        # Применяем фильтры к этому списку
        if filter_date:
            tech_cards_queryset = tech_cards_queryset.filter(flight__date=filter_date)
        if filter_direction:
            tech_cards_queryset = tech_cards_queryset.filter(flight__direction=filter_direction)
        if filter_region:
            tech_cards_queryset = tech_cards_queryset.filter(flight__region=filter_region)

        # Получаем цены за услуги один раз, чтобы не делать это в цикле
        prices = {sp.service_type_id: sp.price_per_unit for sp in ServicePrice.objects.all()}

        # Перебираем отфильтрованные техкарты и рассчитываем стоимость
        for tech_card in tech_cards_queryset.order_by('-created_at'):
            total_cost = 0
            for service in tech_card.services.all():
                price_per_unit = prices.get(service.service_type_id, 0)
                total_cost += service.quantity * price_per_unit

            tech_cards_with_costs.append({
                'tech_card': tech_card,
                'total_cost': total_cost
            })

    context = {
        'form': form,
        'tech_cards_with_costs': tech_cards_with_costs,
    }
    return render(request, 'flights/finance_dashboard.html', context)

@login_required
def finance_manage_services(request, flight_id, tech_card_id):
    """
    Страница деталей техкарты для финансиста.
    Отображает услуги конкретной техкарты с рассчитанной стоимостью.
    """
    flight = get_object_or_404(Flight, pk=flight_id)
    tech_card = get_object_or_404(TechCard, pk=tech_card_id)

    services = Service.objects.filter(tech_card=tech_card).order_by('id')

    prices = {sp.service_type_id: sp.price_per_unit for sp in ServicePrice.objects.all()}

    services_with_costs = []
    total_cost = 0

    for service in services:
        price_per_unit = prices.get(service.service_type_id, 0)
        service_total_cost = service.quantity * price_per_unit
        total_cost += service_total_cost

        services_with_costs.append({
            'service': service,
            'price_per_unit': price_per_unit,
            'service_total_cost': service_total_cost
        })

    context = {
        'flight': flight,
        'tech_card': tech_card,
        'services_with_costs': services_with_costs,
        'total_cost': total_cost,
        'is_finance': True,  # Добавляем флаг, чтобы показать финансовые данные
    }
    return render(request, 'flights/finance_manage_services.html', context)

def link_callback(uri, rel):
    uri = unquote(uri)
    if uri.startswith(settings.STATIC_URL):
        path = finders.find(uri.replace(settings.STATIC_URL, ""))
        if path:
            return path
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        if os.path.exists(path):
            return path
    return uri

def generate_pdf_response(template_name, context, filename):
    template = get_template(template_name)
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Ошибка при генерации PDF', status=500)
    return response


# flights/views.py

@login_required
def export_to_pdf(request, flight_id, tech_card_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    if flight.date_fact:
        try:
            flight.date_fact_obj = datetime.strptime(flight.date_fact, '%Y-%m-%d').date()
        except ValueError:
            flight.date_fact_obj = None
    else:
        flight.date_fact_obj = None

    # --- КОНВЕРТАЦИЯ ДАТЫ ДЛЯ СВЯЗАННОГО РЕЙСА ---
    if flight.linked_flight:
        if flight.linked_flight.date_fact:
            try:
                flight.linked_flight.date_fact_obj = datetime.strptime(flight.linked_flight.date_fact, '%Y-%m-%d').date()
            except ValueError:
                flight.linked_flight.date_fact_obj = None
        else:
            flight.linked_flight.date_fact_obj = None
    # --- КОНЕЦ ДОБАВЛЕННОЙ КОНВЕРТАЦИИ ---
    tech_card = get_object_or_404(TechCard, pk=tech_card_id)
    services = Service.objects.filter(tech_card=tech_card).order_by('service_type__code')

    context = {
        'flight': flight,
        'services': services,
        'is_finance': False,
        'tech_card': tech_card,
        'STATIC_URL': settings.STATIC_URL,
        'MEDIA_URL': settings.MEDIA_URL,
        'is_export': True, # Добавляем флаг для экспорта
    }
    filename = f"tech_card_{flight.id}_{tech_card.id}"
    return generate_pdf_response('flights/export_pdf_template.html', context, filename)

@login_required
def preview_pdf_template(request, flight_id, tech_card_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    tech_card = get_object_or_404(TechCard, pk=tech_card_id)
    services = Service.objects.filter(tech_card=tech_card).order_by('id')

    context = {
        'flight': flight,
        'services': services,
        'is_finance': False,
        'tech_card': tech_card,
        'STATIC_URL': settings.STATIC_URL,
        'MEDIA_URL': settings.MEDIA_URL,
        'is_export': False, # Флаг для предпросмотра
    }

    print("Содержимое переменной tech_card:", tech_card)
    print("ID техкарты из tech_card:", tech_card.id)
    return render(request, 'flights/pdf_template.html', context)

@login_required
def finance_export_to_pdf(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    services = Service.objects.filter(tech_card__flight=flight).order_by('id')
    prices = {sp.service_type_id: sp.price_per_unit for sp in ServicePrice.objects.all()}
    items_to_export = []
    total_cost = 0
    for service in services:
        price_per_unit = prices.get(service.service_type_id, 0)
        service_total_cost = service.quantity * price_per_unit
        total_cost += service_total_cost
        items_to_export.append({
            'service': service,
            'price_per_unit': price_per_unit,
            'service_total_cost': service_total_cost
        })
    context = {
        'flight': flight,
        'items_to_export': items_to_export,
        'total_cost': total_cost,
        'is_finance': True,
    }
    filename = f"financial_report_flight_{flight.flight_num}"
    return generate_pdf_response('flights/pdf_template.html', context, filename)

@login_required
def export_to_excel(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    services = flight.services.all().order_by('id')
    prices = {sp.service_type_id: sp.price_per_unit for sp in ServicePrice.objects.all()}
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="financial_report_flight_{flight.flight_num}.xlsx"'
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Финансовый отчет"
    columns = [
        "Тип услуги", "Описание", "Количество", "Ед. изм.",
        "Цена за ед. (руб.)", "Итого (руб.)"
    ]
    worksheet.append(columns)
    total_cost = 0
    for service in services:
        price_per_unit = prices.get(service.service_type_id, 0)
        service_total_cost = service.quantity * price_per_unit
        total_cost += service_total_cost
        row = [
            service.service_type.name,
            service.description,
            service.quantity,
            service.unit_of_measure,
            price_per_unit,
            service_total_cost,
        ]
        worksheet.append(row)
    worksheet.append([])
    worksheet.append(["Общая стоимость:", "", "", "", "", total_cost])
    workbook.save(response)
    return response

@login_required
def export_to_1c(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    services = flight.services.all().order_by('id')
    prices = {sp.service_type_id: sp.price_per_unit for sp in ServicePrice.objects.all()}
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="report_1c_flight_{flight.flight_num}.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Тип услуги', 'Описание', 'Количество', 'Ед. изм.', 'Цена за ед.', 'Итого'])
    total_cost = 0
    for service in services:
        price_per_unit = prices.get(service.service_type_id, 0)
        service_total_cost = service.quantity * price_per_unit
        total_cost += service_total_cost
        writer.writerow([
            service.service_type.name,
            service.description,
            service.quantity,
            service.unit_of_measure,
            price_per_unit,
            service_total_cost
        ])
    writer.writerow(['Общая стоимость', '', '', '', '', total_cost])
    return response

@csrf_exempt
@require_POST
def update_flight_field(request):
    try:
        flight_id = request.POST.get('flight_id')
        field_name = request.POST.get('field_name')
        value = request.POST.get('value')

        if not flight_id or not field_name:
            return JsonResponse({'status': 'error', 'message': 'Отсутствуют обязательные параметры.'}, status=400)

        with transaction.atomic():
            flight = get_object_or_404(Flight, pk=flight_id)

            if field_name == 'linked_flight':
                # Специальная обработка для поля-внешнего ключа
                linked_flight = None
                if value:
                    linked_flight = get_object_or_404(Flight, pk=value)
                setattr(flight, field_name, linked_flight)
            elif field_name == 'stand':
                # Общая обработка для обычных полей
                setattr(flight, field_name, value)
            else:
                return JsonResponse({'status': 'error', 'message': f"Поле '{field_name}' не может быть обновлено через этот API."}, status=400)

            flight.save()
            return JsonResponse({'status': 'success', 'message': f"Поле '{field_name}' успешно обновлено."})
    except Flight.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': "Рейс не найден."}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"Ошибка при сохранении: {e}"}, status=500)

@login_required
@require_POST
def update_techcard_field(request, tech_card_id):
    is_supervisor = request.user.groups.filter(name='supervisor').exists()

    if not is_supervisor:
        return JsonResponse({'status': 'error', 'message': 'Доступ запрещен'}, status=403)

    try:
        data = json.loads(request.body)
        field_name = data.get('field_name')
        value = data.get('value')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Неверный формат JSON'}, status=400)

    tech_card = None
    if tech_card_id == 0:
        # Ваш блок для создания новой техкарты
        flight_id = data.get('flight_id')
        if not flight_id:
            return JsonResponse({'status': 'error', 'message': 'ID рейса не передан.'}, status=400)

        try:
            with transaction.atomic():
                max_num = TechCard.objects.select_for_update().order_by('-tech_card_num').values_list('tech_card_num', flat=True).first()
                tech_card = TechCard.objects.create(
                    flight_id=flight_id,
                    author=request.user,
                    tech_card_num=max_num + 1 if max_num else 1001
                )
        except IntegrityError:
            return JsonResponse({'status': 'error', 'message': 'Ошибка при создании номера техкарты. Попробуйте снова.'}, status=500)
    else:
        # Ваш блок для поиска существующей техкарты
        tech_card = get_object_or_404(TechCard, pk=tech_card_id)

    try:
        if field_name == 'tech_card_text':
            tech_card.tech_card_text = value
        elif field_name == 'max_takeoff_weight':
            tech_card.max_takeoff_weight = value if value else None
        elif field_name == 'fueler':
            if value:
                firm = get_object_or_404(Firm, pk=value)
                tech_card.fueler = firm
            else:
                tech_card.fueler = None
        elif field_name == 'fuel_quantity':
            tech_card.fuel_quantity = value if value else None
        elif field_name == 'fuel_unit':
            tech_card.fuel_unit = value
        else:
            return JsonResponse({'status': 'error', 'message': 'Недопустимое имя поля'}, status=400)

        tech_card.save()

        return JsonResponse({'status': 'success', 'message': f'Поле {field_name} успешно обновлено.', 'tech_card_id': tech_card.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Ошибка при сохранении: {e}'}, status=500)


def is_superuser(user):
    return user.is_superuser

@login_required # Сначала проверяем, авторизован ли пользователь
@user_passes_test(is_superuser, login_url='/flights/supervisor/') # Затем проверяем, является ли он суперпользователем
def log_list(request):
    form = LogFilterForm(request.GET)
    logs = LogEntry.objects.all().order_by('-action_time')

    if form.is_valid():
        if form.cleaned_data['start_date']:
            logs = logs.filter(action_time__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            logs = logs.filter(action_time__lte=form.cleaned_data['end_date'])
        if form.cleaned_data['user']:
            logs = logs.filter(user=form.cleaned_data['user'])

    context = {
        'logs': logs,
        'form': form,
    }
    return render(request, 'flights/log_list.html', context)

@login_required
def view_services_mobile(request, flight_id, tech_card_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    tech_card = get_object_or_404(TechCard, pk=tech_card_id)
    services = tech_card.services.all().order_by('id')
    form = ServiceForm()

    context = {
        'flight': flight,
        'services': services,
        'tech_card': tech_card,
        'form': form,
        'read_only': True, # Это представление только для чтения
    }
    return render(request, 'flights/manage_services_mobile.html', context)