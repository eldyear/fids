from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import InfTablo, Stoiki, Gates
from django.core.cache import cache
import requests
from datetime import datetime, timedelta
from django.utils import timezone
import logging
import pytz
import json
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)  # Логгер для отладки

def get_flights(direction):
    """Общий метод для получения данных рейсов."""
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    two_hours_ago = now - timedelta(hours=2)  # Время 2 часа назад
    tomorrow_cutoff_time = datetime.combine(tomorrow, datetime.strptime("15:00", "%H:%M").time())

    print(f"Сейчас: {now.strftime('%Y-%m-%d %H:%M')}, Два часа назад: {two_hours_ago.strftime('%Y-%m-%d %H:%M')}")
    print(f"Фильтруем завтрашние рейсы после: {tomorrow_cutoff_time.strftime('%Y-%m-%d %H:%M')}")

    # Фильтруем рейсы
    flights = (
        InfTablo.objects.filter(
            direction=direction,
            date1__gte=today,  # Берем только сегодня и завтра
            date1__lte=tomorrow
        )
        .exclude(
            date1=today,
            time1__lt=two_hours_ago.time()  # Исключаем старые рейсы за 2 часа
        )
        .exclude(
            date1=tomorrow,
            time1__gt=tomorrow_cutoff_time.time()  # Исключаем завтрашние рейсы после 15:00
        )
        .select_related('flight', 'destination', 'status')
        .order_by('date1', 'time1')
    )

    print(f"После фильтрации: {flights.count()} рейсов")
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
            api_key = "3b6985d76246edba67b975560d1f98f8"
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
            'pk': pk
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



@csrf_exempt
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


@csrf_exempt
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



# Страница для лога нажатий
def update_log(request):
    log_entries = UpdateLog.objects.all().order_by('-timestamp')  # Получаем все записи и сортируем по времени
    return render(request, 'app/update_log.html', {'log_entries': log_entries})