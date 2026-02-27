from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import InfTablo, Stoiki, Gates, Status, FlightNumber
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from decouple import config
import requests
from datetime import datetime, timedelta
import logging
import pytz
import json

logger = logging.getLogger(__name__)

def get_flights(direction):
    """Общий метод для получения данных рейсов."""
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    two_hours_ago = now - timedelta(hours=2) # Время 2 часа назад
    tomorrow_cutoff_time = datetime.combine(tomorrow, datetime.strptime("15:00", "%H:%M").time())

    print(f"Сейчас: {now.strftime('%Y-%m-%d %H:%M')}, Два часа назад: {two_hours_ago.strftime('%Y-%m-%d %H:%M')}")
    print(f"Фильтруем завтрашние рейсы после: {tomorrow_cutoff_time.strftime('%Y-%m-%d %H:%M')}\n")

    # Фильтруем рейсы
    flights = (
        InfTablo.objects.filter(
            direction=direction,
            date1__gte=today, # Берем только сегодня и завтра
            date1__lte=tomorrow
        )
        # Дополнительная фильтрация по времени и статусу
        .filter(
            Q(
                # Рейсы, которые попадают в 3 часа назад до 30 часов вперед от текущего времени (для запланированного времени)
                Q(
                    date1=now.date(),
                    time1__gte=(now - timedelta(hours=3)).time()
                ) | Q(
                    date1=(now - timedelta(hours=3)).date(),
                    time1__gte=(now - timedelta(hours=3)).time()
                ) | Q(
                    date1__gt=(now - timedelta(hours=3)).date()
                )
            ) | Q(
                # ИЛИ рейсы, у которых запланированное время уже прошло, но статус все еще активен
                Q(date1__lt=now.date()) |
                Q(date1=now.date(), time1__lt=now.time()),
                status__name_en__in=['CHECK-IN', 'BOARDING', 'CHECK-IN BOARDING', 'DELAYED', 'ASAP', 'EXPECTED']
            )
        )
        .order_by('date1', 'time1')
        .select_related('destination', 'status', 'flight_id')
        .prefetch_related('stoika', 'gate')
    )
    return flights




def serialize_flight(item, lang='en', weather_data=None):
    now_utc = timezone.now().strftime('%H:%M')

    status_name = getattr(item.status, f"name_{lang}") if item.status else None
    if status_name:
        status_name = status_name.replace("-", " ")

    return {
        'flight': item.flight.flights,
        'direction': item.direction,
        'destination': {
            'city_name': getattr(item.destination, f"city_name_{lang}"),
            'iata_code': item.destination.iata_code,
        },
        'stoika': [
            {
                'stoiki': stoika.stoiki,
                'sky_priority': stoika.sky_priority
            }
            for stoika in item.stoika.all()
        ],
        'airline': item.airline,
        'date1': item.date1.strftime('%d.%m.%y'),
        'time1': item.time1.strftime('%H:%M'),
        # 'time1': item.time1.strftime('%H:%M') if item.time1 else None,  # Added conditional check
        'last_date': item.last_date.strftime('%d.%m.%y') if item.last_date else None,
        'last_time': item.last_time.strftime('%H:%M') if item.last_time else None,
        'status': {
            'id': item.status.status_id if item.status else None,
            'name': status_name,  # Используем измененное имя
            'style': item.status.name_en.upper() if item.status else None,
        },
        'server_time': now_utc,
        'weather': {
            'icon': f"/media/weather_icons/SVG/{weather_data['icon']}.svg" if weather_data else None,
            'temperature': f"{weather_data['temperature']}°C" if weather_data else "N/A"
        } if weather_data else None
    }




def get_weather_data(city):
    """Получает и кэширует данные о погоде для заданного города."""
    cache_key = f"weather_data_{city}"
    weather_data = cache.get(cache_key)

    if not weather_data:
        try:
            api_key = config('OPENWEATHER_API_KEY')
            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {"q": city, "appid": api_key, "units": "metric"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            weather_data = {
                'icon': data["weather"][0]["icon"],
                'temperature': int(data["main"]["temp"])
            }
            cache.set(cache_key, weather_data, timeout=600)
        except requests.RequestException as e:
            logger.error(f"Ошибка получения погоды для {city}: {e}")
            weather_data = None

    return weather_data

# Временно для вывода на таблицу рейсов как сайт
def flight_table_view(request):
    """
    Представление для вывода рейсов в таблице с возможностью выбора даты и направления.
    По умолчанию отображаются рейсы на текущий день и направление "Вылет".
    """
    # Получаем выбранную дату из параметров запроса GET.
    date_str = request.GET.get('date', None)
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        # Используем текущую дату, если параметр 'date' отсутствует
        selected_date = timezone.now().date()

    # Получаем выбранное направление. По умолчанию "Вылет" (dep).
    selected_direction = request.GET.get('direction', 'вылет')

    # Определяем направление для фильтрации
    # Значения 'dep' и 'arr' берутся из вашей модели InfTablo.
    direction_map = {
        'вылет': 'dep', # ИСПРАВЛЕНО
        'прилет': 'arr', # ИСПРАВЛЕНО
    }
    direction_for_filter = direction_map.get(selected_direction, 'dep')

    # Определяем текст для отображения в заголовке
    direction_text = 'Вылет' if selected_direction == 'вылет' else 'Прилет'

    # Фильтрация рейсов по выбранной дате и направлению
    flights = (
        InfTablo.objects.filter(
            date1=selected_date,
            direction=direction_for_filter
        )
        .order_by('date1', 'time1')
        .select_related('destination', 'status', 'flight')
        .prefetch_related('stoika', 'gate')
    )

    context = {
        'flights': flights,
        'selected_date': selected_date,
        'selected_direction': selected_direction,
        'direction_text': direction_text,
    }

    # Создаем отдельные списки для стоек и гейтов, чтобы их было легче
    # отобразить в шаблоне.
    # Это ключевой шаг для исправления проблемы, так как в шаблоне
    # невозможно напрямую обращаться к ManyToManyField через `.`
    for flight in flights:
        flight.stoiki_list = [s.stoiki for s in flight.stoika.all()]
        flight.gates_list = [g.gate for g in flight.gate.all()]

    return render(request, 'app/departure_table.html', context)

def tablo_dep(request, lang='en'):
    """Возвращает данные о вылетающих рейсах с учетом выбранного языка."""
    flights = get_flights('dep')  # Получаем все рейсы на вылет
    data = [serialize_flight(item, lang) for item in flights]  # Передаем язык в сериализацию
    return JsonResponse({'data': data}, safe=False)  # Возвращаем данные в формате JSON


def tablo_arr(request, lang='en'):
    """Возвращает данные о вылетающих рейсах с учетом выбранного языка."""
    flights = get_flights('arr')  # Получаем все рейсы на вылет
    data = [serialize_flight(item, lang) for item in flights]  # Передаем язык в сериализацию
    return JsonResponse({'data': data}, safe=False)  # Возвращаем данные в формате JSON


def get_flight_data_check(request, lang, pk=None):
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    print(tomorrow)
    """Возвращает данные рейсов с добавлением информации о погоде."""
    flights = InfTablo.objects.filter(
        direction='dep',
        status__name_en__in=['CHECK-IN', 'CHECK-IN BOARDING'],
        date1__gte=today,
        date1__lte=tomorrow,
    )

    # Фильтрация по стойке, если pk указан
    if pk:
        flights = flights.filter(stoika__stoiki=pk)

    flights = flights.select_related('flight', 'destination').prefetch_related('stoika').order_by('date1')

    data = []
    for item in flights:
        city = item.destination.city_name_ru
        weather_data = get_weather_data(city)
        data.append(serialize_flight(item, lang, weather_data))

    if len(data) > 2:
        return JsonResponse({"error": "Количество рейсов превышает допустимый лимит (2)."}, status=400)

    return JsonResponse({"data": data} if data else {"advert": "Ваша реклама могла бы осветить этот экран!"}, status=200)

def get_flight_data_gate(request, lang, pk=None):
    """Возвращает данные рейсов с добавлением информации о погоде."""
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    flights = InfTablo.objects.filter(
        direction='dep',
        status__name_en='BOARDING',
        date1__gte=today,
        date1__lte=tomorrow,
    )


    # Фильтрация по стойке, если pk указан
    if pk:
        flights = flights.filter(gate__gate=pk)

    flights = flights.select_related('flight', 'destination').prefetch_related('gate').order_by('date1')

    data = []
    for item in flights:
        city = item.destination.city_name_en
        weather_data = get_weather_data(city)
        data.append(serialize_flight(item, lang, weather_data))

    if len(data) > 2:
        return JsonResponse({"error": "Количество рейсов превышает допустимый лимит (2)."}, status=400)

    return JsonResponse({"data": data} if data else {"advert": "Ваша реклама могла бы осветить этот экран!"}, status=200)

def get_flight_data_bag(request, lang, pk=None):
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    """Возвращает данные рейсов."""
    flights = InfTablo.objects.filter(
        direction='arr',
        status__name_en='ARRIVED / BAGGAGE',
        date1__gte=today,
        date1__lte=tomorrow,
    )

    # Фильтрация по стойке, если pk указан
    if pk:
        flights = flights.filter(stoika__stoiki=pk)

    flights = flights.select_related('flight', 'destination').prefetch_related('stoika').order_by('date1')

    data = []
    for item in flights:
        data.append(serialize_flight(item, lang))

    if len(data) > 2:
        return JsonResponse({"error": "Количество рейсов превышает допустимый лимит (2)."}, status=400)

    return JsonResponse({"data": data} if data else {"advert": "Ваша реклама могла бы осветить этот экран!"}, status=200)

def departure(request):
    """Рендерит страницу для вылетающих рейсов."""
    return render(request, 'app/departure_ajax.html')


def arrival(request):
    """Рендерит страницу для прилетающих рейсов."""
    return render(request, 'app/arrival.html')

def iframe_dep(request):
    """Рендерит страницу для прилетающих рейсов."""
    return render(request, 'app/iframe_dep.html')

def iframe_arr(request):
    """Рендерит страницу для прилетающих рейсов."""
    return render(request, 'app/iframe_arr.html')

def deparr(request):
    """Рендерит страницу для прилетающих рейсов."""
    return render(request, 'app/deparr.html')

def my_urls(request):
    """Рендерит страницу для прилетающих рейсов."""
    return render(request, 'app/my_urls.html')


def check_ajax(request, pk):
    """Рендерит страницу для проверки рейсов по стойке и получает данные о рейсах."""
    lang = request.GET.get('lang', 'en')  # Получаем язык из параметров запроса, если он есть
    flights_data = get_flight_data_check(request, lang, pk)  # Получаем данные рейсов

    # Проверяем, если данные были получены
    if 'data' in flights_data:
        return render(request, 'app/map.html', {
            'flights': flights_data['data'],  # Передаем отфильтрованные рейсы в шаблон
            'lang': lang,
            'pk': pk,
            'mapbox_token': config('MAPBOX_TOKEN', default='')
        })
    else:
        # Если данных нет, можем передать сообщение о рекламе или ошибке
        return render(request, 'app/check_ajax.html', {
            'advert': flights_data.get('advert', 'Нет данных для отображения'),
            'lang': lang,
            'pk': pk
        })

def gate(request, pk):
    """Рендерит страницу для проверки рейсов по стойке и получает данные о рейсах."""
    lang = request.GET.get('lang', 'en')  # Получаем язык из параметров запроса, если он есть
    flights_data = get_flight_data_gate(request, lang, pk)  # Получаем данные рейсов

    # Проверяем, если данные были получены
    if 'data' in flights_data:
        return render(request, 'app/gate.html', {
            'flights': flights_data['data'],  # Передаем отфильтрованные рейсы в шаблон
            'lang': lang,
            'pk': pk
        })
    else:
        # Если данных нет, можем передать сообщение о рекламе или ошибке
        return render(request, 'app/gate.html', {
            'advert': flights_data.get('advert', 'Нет данных для отображения'),
            'lang': lang,
            'pk': pk
        })



def baggage(request, pk):
    """Рендерит страницу для проверки рейсов по стойке и получает данные о рейсах."""
    lang = request.GET.get('lang', 'en')  # Получаем язык из параметров запроса, если он есть
    flights_data = get_flight_data_check(request, lang, pk)  # Получаем данные рейсов

    # Проверяем, если данные были получены
    if 'data' in flights_data:
        return render(request, 'app/baggage_ajax.html', {
            'flights': flights_data['data'],  # Передаем отфильтрованные рейсы в шаблон
            'lang': lang,
            'pk': pk
        })
    else:
        # Если данных нет, можем передать сообщение о рекламе или ошибке
        return render(request, 'app/baggage_ajax.html', {
            'advert': flights_data.get('advert', 'Нет данных для отображения'),
            'lang': lang,
            'pk': pk
        })


from django.contrib import messages
from .utils.services import FlightAPIClient
from .models import UpdateLog



@csrf_exempt # !!! ВНИМАНИЕ: Используйте это только для AJAX, который вы полностью контролируете,
             # или убедитесь, что ваш AJAX-запрос включает CSRF-токен в заголовках.
             # Для вашего случая, где запрос идет с вашей же страницы админа, это нормально.
def update_flights(request):
    """
    Обрабатывает запрос на обновление рейсов.
    При POST-запросе запускает импорт и возвращает JSON-ответ,
    который может содержать список рейсов для подтверждения.
    """
    if request.method == "POST":
        # Запись в лог перед обработкой запроса
        UpdateLog.objects.create()

        today_str = datetime.now().strftime("%d.%m.%Y")
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

        op_types = ["O", "P"]  # Вылеты и прилеты

        all_results = []
        for op_type in op_types:
            result_today = FlightAPIClient.save_flights_to_db(op_type, today_str)
            result_tomorrow = FlightAPIClient.save_flights_to_db(op_type, tomorrow_str)
            all_results.append(result_today)
            all_results.append(result_tomorrow)

        # Собираем все рейсы, требующие подтверждения, и сообщения
        flights_to_confirm_overall = []
        initial_messages = []

        for res in all_results:
            if "confirm_flights" in res:
                flights_to_confirm_overall.extend(res["confirm_flights"])
                if "initial_message" in res:
                    initial_messages.append(res["initial_message"])
            elif "success" in res:
                initial_messages.append(res["success"])
            elif "error" in res:
                initial_messages.append(res["error"])

        if flights_to_confirm_overall:
            return JsonResponse({
                "status": "requires_confirmation",
                "flights": flights_to_confirm_overall,
                "initial_messages": initial_messages # Сообщения о рейсах, которые не требовали подтверждения
            })
        else:
            # Если нет рейсов на подтверждение, объединяем все сообщения об успехе/ошибке
            final_message = " ".join(initial_messages)
            return JsonResponse({"status": "completed", "message": final_message})

    # Для GET-запроса, рендерим страницу с фильтрацией рейсов по статусу
    check_in_flights = InfTablo.objects.filter(status__name_en__in=["CHECK-IN", "CHECK-IN BOARDING"])
    boarding_flights = InfTablo.objects.filter(status__name_en__in=["BOARDING", "CHECK-IN BOARDING"])
    arrived_flights = InfTablo.objects.filter(status__name_en="ARRIVED").order_by("-date1", "-time1")[:5]

    return render(request, "app/update_flights.html", {
        "check_in_flights": check_in_flights,
        "boarding_flights": boarding_flights,
        "arrived_flights": arrived_flights
    })


@csrf_exempt # !!! Используйте осторожно, как и выше.
def confirm_delay_ajax(request):
    """
    Принимает AJAX-запрос для подтверждения или пропуска задержанного рейса.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flight_id = data.get('flight_id')
            decision = data.get('decision') # 'apply' или 'skip'
            new_status_text = data.get('new_status_text')
            new_time1 = data.get('new_time1')
            new_last_time = data.get('new_last_time')

            if not all([flight_id, decision, new_status_text]):
                return JsonResponse({"error": "Недостаточно данных для подтверждения."}, status=400)

            if decision == 'apply':
                result = FlightAPIClient.apply_confirmed_delay(flight_id, new_status_text, new_time1, new_last_time)
                return JsonResponse(result)
            elif decision == 'skip':
                return JsonResponse({"success": f"Рейс ID {flight_id} пропущен администратором."})
            else:
                return JsonResponse({"error": "Неизвестное решение."}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Некорректный JSON-формат."}, status=400)
        except Exception as e:
            logger.error(f"Ошибка в confirm_delay_ajax: {e}", exc_info=True)
            return JsonResponse({"error": f"Неожиданная ошибка сервера: {str(e)}"}, status=500)
    return JsonResponse({"error": "Только POST-запросы."}, status=405)


def update_stoika(request, flight_id):
    """Обновление ManyToMany поля стоек"""
    if request.method == "POST":
        flight = InfTablo.objects.get(id=flight_id)
        stoika_input = request.POST.get("stoika", "").strip()

        if stoika_input:
            stoika_numbers = [s.strip() for s in stoika_input.split(",") if s.strip().isdigit()]
            stoika_objects = Stoiki.objects.filter(stoiki__in=stoika_numbers)

            existing_numbers = set(stoika_objects.values_list("stoiki", flat=True))
            missing_numbers = set(stoika_numbers) - existing_numbers

            if missing_numbers:
                messages.error(request, f"Стойки {', '.join(missing_numbers)} не найдены.")
            else:
                flight.stoika.set(stoika_objects)
                messages.success(request, "Стойки успешно обновлены.")

    return redirect("update_flights")

def update_sky_priority(request, flight_id):
    if request.method == "POST":
        flight = get_object_or_404(InfTablo, id=flight_id)
        sky_priority_input = request.POST.get("sky_priority_numbers", "").strip()

        # Сбрасываем sky_priority для всех стоек рейса
        for stoika in flight.stoika.all():
            stoika.sky_priority = False
            stoika.save()

        if sky_priority_input:
            sky_priority_numbers = [s.strip() for s in sky_priority_input.split(",") if s.strip().isdigit()]
            sky_priority_objects = Stoiki.objects.filter(stoiki__in=sky_priority_numbers)

            existing_numbers = set(sky_priority_objects.values_list("stoiki", flat=True))
            missing_numbers = set(sky_priority_numbers) - existing_numbers

            if missing_numbers:
                messages.error(request, f"Стойки {', '.join(missing_numbers)} не найдены.")
            else:
                # Устанавливаем sky_priority для выбранных стоек
                for stoika in sky_priority_objects:
                    stoika.sky_priority = True
                    stoika.save()
                messages.success(request, "Sky Priority стойки успешно обновлены.")
        else:
            messages.success(request, "Sky Priority стойки успешно сброшены.")

    return redirect("update_flights")


def update_gate(request, flight_id):
    """Обновление ManyToMany поля гейтов"""
    if request.method == "POST":
        flight = InfTablo.objects.get(id=flight_id)
        gate_input = request.POST.get("gate", "").strip()

        if gate_input:
            gate_numbers = [g.strip() for g in gate_input.split(",") if g.strip().isdigit()]
            gate_objects = Gates.objects.filter(id__in=gate_numbers)

            existing_numbers = set(gate_objects.values_list("gate", flat=True))
            missing_numbers = set(gate_numbers) - existing_numbers

            if missing_numbers:
                messages.error(request, f"Гейты {', '.join(missing_numbers)} не найдены.")
            else:
                flight.gate.set(gate_objects)
                messages.success(request, "Гейты успешно обновлены.")

    return redirect("update_flights")

def update_baggage(request, flight_id):
    """Обновление ManyToMany поля карусели"""
    if request.method == "POST":
        flight = InfTablo.objects.get(id=flight_id)
        baggage_input = request.POST.get("stoika", "").strip()

        if baggage_input:
            baggage_numbers = [g.strip() for g in baggage_input.split(",") if g.strip().isdigit()]
            baggage_objects = Gates.objects.filter(id__in=baggage_numbers)

            existing_numbers = set(baggage_objects.values_list("stoiki", flat=True))
            missing_numbers = set(baggage_numbers) - existing_numbers

            if missing_numbers:
                messages.error(request, f"Гейты {', '.join(missing_numbers)} не найдены.")
            else:
                flight.gate.set(baggage_objects)
                messages.success(request, "Гейты успешно обновлены.")

    return redirect("update_flights")

# Страницы интерфейса агентов
def agent_registration_view(request, stand_number):
    """
    Отображает интерфейс для агента на стойке регистрации,
    фильтруя рейсы по статусу, временному диапазону и направлению "Вылет".
    """
    now_local = timezone.localtime(timezone.now())
    time_threshold_past_local = now_local - timedelta(hours=3)
    time_threshold_future_local = now_local + timedelta(hours=10)

    try:
        departed_status = Status.objects.get(name_en='DEPARTED')
    except Status.DoesNotExist:
        departed_status = None
        logger.warning("Статус 'DEPARTED' не найден в базе данных. Фильтрация по статусу может быть неточной.")

    flights_query = InfTablo.objects.filter(direction='dep')

    if departed_status:
        flights_query = flights_query.exclude(status=departed_status)

    filtered_flights = []
    for flight in flights_query:
        if flight.date1 and flight.time1:
            naive_flight_datetime = datetime.combine(flight.date1, flight.time1)
            flight_datetime_local = timezone.make_aware(naive_flight_datetime, timezone=timezone.get_current_timezone())

            if time_threshold_past_local <= flight_datetime_local <= time_threshold_future_local:
                filtered_flights.append(flight)

    filtered_flights.sort(key=lambda f: datetime.combine(f.date1, f.time1))

    # Определяем текущий активный рейс на этой стойке
    current_flight = None
    current_flight_obj = None
    for flight in filtered_flights:
        if any(str(stoika.stoiki) == str(stand_number) for stoika in flight.stoika.all()):
            if flight.status and flight.status.name_en in ['CHECK-IN', 'CHECK-IN BOARDING']:
                current_flight = f"{flight.flight.flights}_{flight.date1.strftime('%Y-%m-%d')}"
                current_flight_obj = flight
                break

    context = {
        'stand_number': stand_number,
        'flights': filtered_flights,
        'page_title': f'Рабочее место агента (Стойка {stand_number})',
        'current_flight': current_flight,
        'current_flight_obj': current_flight_obj,
    }
    return render(request, 'app/agent_registration.html', context)

def agent_boarding_view(request, gate_number):
    """
    Отображает интерфейс для агента на гейте посадки,
    фильтруя рейсы по статусу, временному диапазону и направлению "Вылет".
    """
    now_local = timezone.localtime(timezone.now())
    time_threshold_past_local = now_local - timedelta(hours=3)
    time_threshold_future_local = now_local + timedelta(hours=10)

    try:
        departed_status = Status.objects.get(name_en='DEPARTED')
    except Status.DoesNotExist:
        departed_status = None
        logger.warning("Статус 'DEPARTED' не найден в базе данных. Фильтрация по статусу может быть неточной.")

    flights_query = InfTablo.objects.filter(direction='dep')

    if departed_status:
        flights_query = flights_query.exclude(status=departed_status)

    filtered_flights = []
    for flight in flights_query:
        if flight.date1 and flight.time1:
            naive_flight_datetime = datetime.combine(flight.date1, flight.time1)
            flight_datetime_local = timezone.make_aware(naive_flight_datetime, timezone=timezone.get_current_timezone())

            if time_threshold_past_local <= flight_datetime_local <= time_threshold_future_local:
                filtered_flights.append(flight)

    filtered_flights.sort(key=lambda f: datetime.combine(f.date1, f.time1))

    # Определяем текущий активный рейс на этом гейте
    current_flight = None
    current_flight_obj = None
    for flight in filtered_flights:
        if any(str(gate.gate) == str(gate_number) for gate in flight.gate.all()):
            if flight.status and flight.status.name_en in ['BOARDING', 'CHECK-IN BOARDING']:
                current_flight = f"{flight.flight.flights}_{flight.date1.strftime('%Y-%m-%d')}"
                current_flight_obj = flight
                break

    context = {
        'gate_number': gate_number,
        'flights': filtered_flights,
        'page_title': f'Рабочее место агента (Гейт {gate_number})',
        'current_flight': current_flight,
        'current_flight_obj': current_flight_obj,
    }
    return render(request, 'app/agent_boarding.html', context)

# -----------------------------------------------------------
# API ФУНКЦИИ (ОБНОВЛЕНО)
# -----------------------------------------------------------

@csrf_exempt
def start_registration_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flight_number_str = data.get('flight_number')
            flight_date_str = data.get('flight_date')
            stand_number_str = data.get('stand_number')

            if not flight_number_str or not flight_date_str or not stand_number_str:
                return JsonResponse({'status': 'error', 'message': 'Отсутствует номер рейса, дата рейса или стойки.'}, status=400)

            try:
                flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Неверный формат даты рейса. ИспользуйтеYYYY-MM-DD.'}, status=400)

            with transaction.atomic():
                flight_num_obj = get_object_or_404(FlightNumber, flights=flight_number_str)
                flight = get_object_or_404(InfTablo, flight=flight_num_obj, date1=flight_date)
                stand_obj = get_object_or_404(Stoiki, stoiki=stand_number_str)

                status_registration = get_object_or_404(Status, name_en='CHECK-IN')
                status_boarding = get_object_or_404(Status, name_en='BOARDING')
                status_checkin_boarding = get_object_or_404(Status, name_en='CHECK-IN BOARDING')

                if stand_obj not in flight.stoika.all():
                    flight.stoika.add(stand_obj)
                    logger.info(f"Стойка {stand_number_str} добавлена к рейсу {flight_number_str} на {flight_date_str}.")
                else:
                    logger.info(f"Стойка {stand_number_str} уже была добавлена к рейсу {flight_number_str} на {flight_date_str}.")

                current_flight_status = flight.status

                # Исправлено: сначала проверяем, что статус не None
                if not current_flight_status or current_flight_status.name_en not in ['CHECK-IN', 'CHECK-IN BOARDING']:
                    flight.status = status_registration
                    flight.save()
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменён на 'Регистрация'.")
                else:
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} уже 'Регистрация' или 'Регистрация_Посадка'. Изменений не требуется.")

                flight.save()

                return JsonResponse({'status': 'success', 'message': f'Регистрация рейса {flight_number_str} на {flight_date_str} начата на стойке {stand_number_str}.'})
        except InfTablo.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Рейс {flight_number_str} на {flight_date_str} не найден.'}, status=404)
        except FlightNumber.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Номер рейса {flight_number_str} не найден в справочнике FlightNumber.'}, status=404)
        except Stoiki.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Стойка {stand_number_str} не найдена.'}, status=404)
        except Status.DoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': f'Ошибка: Отсутствует статус в таблице Status. Убедитесь, что существуют: "CHECK-IN", "BOARDING", "CHECK-IN BOARDING".'}, status=500)
        except Exception as e:
            logger.error(f"Ошибка при начале регистрации для рейса {flight_number_str} на {flight_date_str} на стойке {stand_number_str}: {e}")
            return JsonResponse({'status': 'error', 'message': f'Произошла ошибка: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Недопустимый метод запроса.'}, status=405)


@csrf_exempt
def end_registration_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flight_number_str = data.get('flight_number')
            flight_date_str = data.get('flight_date')
            stand_number_str = data.get('stand_number')

            if not flight_number_str or not flight_date_str or not stand_number_str:
                return JsonResponse({'status': 'error', 'message': 'Отсутствует номер рейса, дата рейса или стойки.'}, status=400)

            flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()
            with transaction.atomic():
                flight_num_obj = get_object_or_404(FlightNumber, flights=flight_number_str)
                flight = get_object_or_404(InfTablo, flight=flight_num_obj, date1=flight_date)
                stand_obj = get_object_or_404(Stoiki, stoiki=stand_number_str)

                # Удаляем связь стойки с рейсом
                if stand_obj in flight.stoika.all():
                    flight.stoika.remove(stand_obj)

                # Если больше нет ни одной стойки — меняем статус
                if flight.stoika.count() == 0:
                    status_checkin_closed = get_object_or_404(Status, name_en='CHECK-IN CLOSED')
                    flight.status = status_checkin_closed
                    flight.save()
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменён на 'Регистрация закрыта'.")
                    return JsonResponse({'status': 'success', 'message': 'Регистрация завершена для всех стоек. Статус рейса изменён.'})
                else:
                    logger.info(f"Регистрация завершена для стойки {stand_number_str}, статус рейса не изменён.")
                    return JsonResponse({'status': 'success', 'message': 'Регистрация завершена для этой стойки. Статус рейса не изменён.'})

        except InfTablo.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Рейс {flight_number_str} на {flight_date_str} не найден.'}, status=404)
        except FlightNumber.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Номер рейса {flight_number_str} не найден в справочнике FlightNumber.'}, status=404)
        except Status.DoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': f'Ошибка: Отсутствует статус в таблице Status. Убедитесь, что существуют: "CHECK-IN", "CHECK-IN BOARDING", "BOARDING", "CHECK-IN CLOSED".'}, status=500)
        except Exception as e:
            logger.error(f'Ошибка при завершении регистрации: {e}')
            return JsonResponse({'status': 'error', 'message': f'Произошла ошибка: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Недопустимый метод запроса.'}, status=405)


@csrf_exempt
def start_boarding_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flight_number_str = data.get('flight_number')
            flight_date_str = data.get('flight_date')
            gate_number_str = data.get('gate_number')

            if not flight_number_str or not flight_date_str or not gate_number_str:
                return JsonResponse({'status': 'error', 'message': 'Отсутствует номер рейса, дата рейса или гейта.'}, status=400)

            try:
                flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Неверный формат даты рейса. Используйте YYYY-MM-DD.'}, status=400)

            with transaction.atomic():
                flight_num_obj = get_object_or_404(FlightNumber, flights=flight_number_str)
                flight = get_object_or_404(InfTablo, flight=flight_num_obj, date1=flight_date)

                gate_obj = get_object_or_404(Gates, gate=gate_number_str)

                status_registration = get_object_or_404(Status, name_en='CHECK-IN')
                status_boarding = get_object_or_404(Status, name_en='BOARDING')
                status_checkin_boarding = get_object_or_404(Status, name_en='CHECK-IN BOARDING')

                if gate_obj not in flight.gate.all():
                    flight.gate.add(gate_obj)
                    logger.info(f"Гейт {gate_number_str} добавлен к рейсу {flight_number_str} на {flight_date_str}.")
                else:
                    logger.info(f"Гейт {gate_number_str} уже был добавлен к рейсу {flight_number_str} на {flight_date_str}.")

                current_flight_status = flight.status # Запоминаем текущий статус

                if current_flight_status == status_registration:
                    flight.status = status_checkin_boarding
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Регистрация' на 'Регистрация_Посадка'.")
                else:
                    if current_flight_status != status_boarding: # Если текущий статус НЕ "Посадка"
                        flight.status = status_boarding
                        logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с '{current_flight_status.name_en if current_flight_status else 'неизвестный/нет'}' на 'Посадка'.")
                    else: # Если текущий статус УЖЕ "Посадка"
                        logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} уже 'Посадка'. Изменений не требуется.")

                flight.save()

                return JsonResponse({'status': 'success', 'message': f'Посадка рейса {flight_number_str} на {flight_date_str} начата на гейте {gate_number_str}.'})
        except InfTablo.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Рейс {flight_number_str} на {flight_date_str} не найден.'}, status=404)
        except FlightNumber.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Номер рейса {flight_number_str} не найден в справочнике FlightNumber.'}, status=404)
        except Gates.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Гейт {gate_number_str} не найден.'}, status=404)
        except Status.DoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': f'Ошибка: Отсутствует статус в таблице Status. Убедитесь, что существуют: "CHECK-IN", "BOARDING", "CHECK-IN BOARDING".'}, status=500)
        except Exception as e:
            logger.error(f"Ошибка при начале посадки для рейса {flight_number_str} на {flight_date_str} на гейте {gate_number_str}: {e}")
            return JsonResponse({'status': 'error', 'message': f'Произошла ошибка: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Недопустимый метод запроса.'}, status=405)


@csrf_exempt
def end_boarding_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flight_number_str = data.get('flight_number')
            flight_date_str = data.get('flight_date') # Ожидаем дату в формате 'YYYY-MM-DD'

            if not flight_number_str or not flight_date_str:
                return JsonResponse({'status': 'error', 'message': 'Номер рейса и дата обязательны.'}, status=400)

            flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()

            with transaction.atomic():
                # Находим FlightNumber
                try:
                    flight_num_obj = FlightNumber.objects.get(flights=flight_number_str)
                except FlightNumber.DoesNotExist:
                    # Если FlightNumber не найден, пытаемся найти InfTablo по номеру рейса (если он уникален)
                    # В этом случае, логика может быть сложнее, и, возможно, потребуется ручное сопоставление.
                    # Для простоты, пока будем считать, что FlightNumber существует.
                    return JsonResponse({'status': 'error', 'message': f'Номер рейса {flight_number_str} не найден в справочнике FlightNumber.'}, status=404)


                # Находим рейс в InfTablo по flight_id (связанному с flight_num_obj) и дате
                flight = InfTablo.objects.get(flight_id=flight_num_obj, date1=flight_date)

                # Получаем статус "BOARDING"
                # Используем Q-объекты для поиска одного из возможных статусов
                boarding_status = Status.objects.filter(Q(name_en='BOARDING') | Q(name_en='CHECK-IN BOARDING')).first()

                # Получаем статус "ASAP"
                asap_status = Status.objects.get(name_en='ASAP')

                # Если текущий статус "BOARDING" или "CHECK-IN BOARDING", меняем его на "ASAP"
                if flight.status == boarding_status:
                    flight.status = asap_status
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Посадка' на 'ASAP'.")
                elif flight.status.name_en == 'CHECK-IN BOARDING': # Если был "Регистрация-Посадка", меняем на "Регистрация"
                     checkin_status = Status.objects.get(name_en='CHECK-IN')
                     flight.status = checkin_status
                     logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Регистрация_Посадка' на 'Регистрация'.")

                flight.save()

                return JsonResponse({'status': 'success', 'message': f'Посадка рейса {flight_number_str} на {flight_date_str} завершена.'})
        except InfTablo.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Рейс {flight_number_str} на {flight_date_str} не найден.'}, status=404)
        except FlightNumber.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Номер рейса {flight_number_str} не найден в справочнике FlightNumber.'}, status=404)
        except Status.DoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': f'Ошибка: Отсутствует статус в таблице Status. Убедитесь, что существуют: "BOARDING", "CHECK-IN BOARDING", "ASAP", "CHECK-IN".'}, status=500)
        except Exception as e:
            logger.error(f"Ошибка при завершении посадки для рейса {flight_number_str} на {flight_date_str}: {e}")
            return JsonResponse({'status': 'error', 'message': f'Произошла ошибка: {str(e)}'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Недопустимый метод запроса.'}, status=405)



def get_active_registrations_api(request):
    # Получаем текущее время в UTC
    now_utc = timezone.now()

    # Определяем местный часовой пояс (должен соответствовать TIME_ZONE в settings.py)
    # Если TIME_ZONE = 'Asia/Bishkek', то здесь используем 'Asia/Bishkek'
    # Если вы не уверены, какой часовой пояс используется в ваших данных date1/time1,
    # попробуйте для начала 'Asia/Bishkek', так как вы из Кыргызстана.
    local_timezone = pytz.timezone('Asia/Bishkek')

    # Конвертируем текущее время UTC в локальное время для корректных сравнений с date1 и time1
    now_local = now_utc.astimezone(local_timezone)

    # Расширенное окно для диспетчера: от -2 часов назад до +4 часов вперед от текущего ЛОКАЛЬНОГО времени
    start_time_window_local = now_local - timedelta(hours=2)
    end_time_window_local = now_local + timedelta(hours=4)

    # print(f"--- Отладка фильтрации рейсов ---")
    # print(f"Текущее время сервера (UTC): {now_utc}")
    # print(f"Текущее время локальное ({now_local.tzname()}): {now_local}")
    # print(f"Начало окна фильтрации (локальное): {start_time_window_local}")
    # print(f"Конец окна фильтрации (локальное): {end_time_window_local}")
    # print(f"Фильтруемые статусы: ['CHECK-IN', 'BOARDING', 'CHECK-IN BOARDING', 'LAST CALL']")

    flights_query = InfTablo.objects.filter(
        (
            Q(date1__gt=start_time_window_local.date()) |
            Q(date1=start_time_window_local.date(), time1__gte=start_time_window_local.time())
        ) &
        (
            Q(date1__lt=end_time_window_local.date()) |
            Q(date1=end_time_window_local.date(), time1__lte=end_time_window_local.time())
        ) &
        Q(status__name_en__in=['CHECK-IN', 'BOARDING', 'CHECK-IN BOARDING', 'LAST CALL'])
    ).order_by('date1', 'time1').select_related('destination', 'status', 'flight').prefetch_related('stoika', 'gate')

    # print(f"Количество найденных рейсов ДО формирования списка: {flights_query.count()}")
    # print(f"--- Найденные рейсы: ---")
    for f in flights_query:
        flight_num = f.flight.flights if f.flight else 'N/A'
        dest_name = f.destination.city_name_en if f.destination else 'N/A'
        status_name = f.status.name_en if f.status else 'N/A'
    #     print(f"  ID={f.id}, Flight={flight_num}, Destination={dest_name}, Date={f.date1}, Time={f.time1}, Status={status_name}")
    # print(f"--- Конец списка найденных рейсов ---")

    flight_list = []
    for flight in flights_query:
        # ... (ваш существующий код для формирования stoiki_data, gates_data и добавления в flight_list)
        # Убедитесь, что здесь все поля, которые использует JS, присутствуют
        stoiki_data = []
        for stoika in flight.stoika.all():
            stoiki_data.append({
                "Number": stoika.stoiki,
                "SkyPriority": stoika.sky_priority
            })

        gates_data = []
        for gate in flight.gate.all():
            gates_data.append({
                "Number": gate.gate
            })

        flight_list.append({
            "id": flight.id,
            "flight": flight.flight.flights if flight.flight else None,
            "destination": {
                "name_ru": flight.destination.city_name_ru,
                "name_en": flight.destination.city_name_en,
            },
            "time1": flight.time1.strftime('%H:%M:%S') if flight.time1 else None,
            "status": {
                "name_ru": flight.status.name_ru,
                "name_en": flight.status.name_en,
            },
            "stoika": stoiki_data, # Оставляем для JS, даже если не отображаем
            "gate": gates_data,   # Оставляем для JS, даже если не отображаем
            # ... другие поля, которые могут быть полезны для отладки или скрытого использования
        })
    return JsonResponse(flight_list, safe=False)


# Страница для лога нажатий
def update_log(request):
    log_entries = UpdateLog.objects.all().order_by('-timestamp')  # Получаем все записи и сортируем по времени
    return render(request, 'app/update_log.html', {'log_entries': log_entries})