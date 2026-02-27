from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import InfTablo, Stoiki, Gates, FlightNumber, Status
from django.core.cache import cache
import requests
from datetime import datetime, timedelta
from django.utils import timezone
import logging
import pytz
from django.db.models import Q # Добавляем импорт Q
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib import messages
import json

logger = logging.getLogger(__name__) # Логгер для отладки

def get_flights(direction):
    """Общий метод для получения данных рейсов."""
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    two_hours_ago = now - timedelta(hours=2) # Время 2 часа назад
    tomorrow_cutoff_time = datetime.combine(tomorrow, datetime.strptime("15:00", "%H:%M").time())

    print(f"Сейчас: {now.strftime('%Y-%m-%d %H:%M')}, Два часа назад: {two_hours_ago.strftime('%Y-%m-%d %H:%M')}")
    print(f"Фильтруем завтрашние рейсы после: {tomorrow_cutoff_time.strftime('%Y-%m-%d %H:%M')}")

    # Фильтруем рейсы
    flights = (
        InfTablo.objects.filter(
            direction=direction,
            date1__gte=today, # Берем только сегодня и завтра
            date1__lte=tomorrow
        )
        .exclude(
            date1=today,
            time1__lt=two_hours_ago.time() # Исключаем старые рейсы за 2 часа
        )
        .exclude(
            date1=tomorrow,
            time1__gt=tomorrow_cutoff_time.time() # Исключаем завтрашние рейсы после 15:00
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
        # 'time1': item.time1.strftime('%H:%M') if item.time1 else None, # Added conditional check
        'last_date': item.last_date.strftime('%d.%m.%y') if item.last_date else None,
        'last_time': item.last_time.strftime('%H:%M') if item.last_time else None,
        'status': {
            'id': item.status.status_id if item.status else None,
            'name': status_name, # Используем измененное имя
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
    flights = get_flights('dep') # Получаем все рейсы на вылет
    data = [serialize_flight(item, lang) for item in flights] # Передаем язык в сериализацию
    return JsonResponse({'data': data}, safe=False) # Возвращаем данные в формате JSON

def tablo_arr(request, lang='en'):
    """Возвращает данные о вылетающих рейсах с учетом выбранного языка."""
    flights = get_flights('arr') # Получаем все рейсы на вылет
    data = [serialize_flight(item, lang) for item in flights] # Передаем язык в сериализацию
    return JsonResponse({'data': data}, safe=False) # Возвращаем данные в формате JSON

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
    lang = request.GET.get('lang', 'en') # Получаем язык из параметров запроса, если он есть
    flights_data = get_flight_data_check(request, lang, pk) # Получаем данные рейсов

    # Проверяем, если данные были получены
    if 'data' in flights_data:
        return render(request, 'app/map.html', {
            'flights': flights_data['data'], # Передаем отфильтрованные рейсы в шаблон
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
    lang = request.GET.get('lang', 'en') # Получаем язык из параметров запроса, если он есть
    flights_data = get_flight_data_gate(request, lang, pk) # Получаем данные рейсов

    # Проверяем, если данные были получены
    if 'data' in flights_data:
        return render(request, 'app/gate.html', {
            'flights': flights_data['data'], # Передаем отфильтрованные рейсы в шаблон
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
    lang = request.GET.get('lang', 'en') # Получаем язык из параметров запроса, если он есть
    flights_data = get_flight_data_check(request, lang, pk) # Получаем данные рейсов

    # Проверяем, если данные были получены
    if 'data' in flights_data:
        return render(request, 'app/baggage_ajax.html', {
            'flights': flights_data['data'], # Передаем отфильтрованные рейсы в шаблон
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

def update_flights(request):
    """Обновление рейсов и фильтрация по статусу"""
    if request.method == "POST":
        try:
            # Запись в лог перед обработкой запроса
            UpdateLog.objects.create()

            today = datetime.now().strftime("%d.%m.%Y")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
            op_types = ["O", "P"] # Вылеты и прилеты

            delayed_flights = []
            updated_flights = []
            new_flights = []

            for op_type in op_types:
                result_today = FlightAPIClient.save_flights_to_db(op_type, today)
                result_tomorrow = FlightAPIClient.save_flights_to_db(op_type, tomorrow)
                
                if isinstance(result_today, dict):
                    if "error" in result_today:
                        messages.error(request, result_today["error"])
                    else:
                        if "delayed" in result_today:
                            delayed_flights.extend(result_today["delayed"])
                        if "updated_flights" in result_today:
                            updated_flights.extend(result_today["updated_flights"])
                        if "new" in result_today:
                            new_flights.append(result_today["new"])
                
                if isinstance(result_tomorrow, dict):
                    if "error" in result_tomorrow:
                        messages.error(request, result_tomorrow["error"])
                    else:
                        if "delayed" in result_tomorrow:
                            delayed_flights.extend(result_tomorrow["delayed"])
                        if "updated_flights" in result_tomorrow:
                            updated_flights.extend(result_tomorrow["updated_flights"])
                        if "new" in result_tomorrow:
                            new_flights.append(result_tomorrow["new"])

            # Формируем сообщения о результатах обновления
            if delayed_flights:
                delayed_message = f"⚠️ Внимание! Задержанные рейсы ({len(delayed_flights)}): {', '.join(delayed_flights)}"
                messages.error(request, delayed_message)
            
            # Формируем единое сообщение для обновленных и новых рейсов
            update_message = []
            if updated_flights:
                update_message.append(f"Обновлено рейсов: {len(updated_flights)}")
            
            if new_flights:
                total_new = sum(new_flights)
                update_message.append(f"Добавлено новых рейсов: {total_new}")

            if update_message:
                messages.success(request, " | ".join(update_message))

        except Exception as e:
            messages.error(request, f"Произошла ошибка при обновлении данных: {str(e)}")

    # Фильтруем рейсы по статусу
    check_in_flights = InfTablo.objects.filter(status__name_en__in=["CHECK-IN", "CHECK-IN BOARDING"])
    boarding_flights = InfTablo.objects.filter(status__name_en__in=["BOARDING", "CHECK-IN BOARDING"])
    arrived_flights = InfTablo.objects.filter(status__name_en="ARRIVED").order_by("-date1", "-time1")[:5]

    context = {
        "check_in_flights": check_in_flights,
        "boarding_flights": boarding_flights,
        "arrived_flights": arrived_flights
    }

    response = render(request, "app/update_flights.html", context)
    response['Content-Type'] = 'text/html'
    return response

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

    context = {
        'stand_number': stand_number,
        'flights': filtered_flights,
        'page_title': f'Рабочее место агента (Стойка {stand_number})'
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

    context = {
        'gate_number': gate_number,
        'flights': filtered_flights,
        'page_title': f'Рабочее место агента (Гейт {gate_number})'
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

                current_flight_status = flight.status # Запоминаем текущий статус

                if current_flight_status == status_boarding:
                    flight.status = status_checkin_boarding
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Посадка' на 'Регистрация_Посадка'.")
                else:
                    if current_flight_status != status_registration: # Если текущий статус НЕ "Регистрация"
                        flight.status = status_registration
                        logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с '{current_flight_status.name_en if current_flight_status else 'неизвестный/нет'}' на 'Регистрация'.")
                    else: # Если текущий статус УЖЕ "Регистрация"
                        logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} уже 'Регистрация'. Изменений не требуется.")
                
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

            if not flight_number_str or not flight_date_str:
                return JsonResponse({'status': 'error', 'message': 'Отсутствует номер рейса или дата рейса.'}, status=400)

            try:
                flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Неверный формат даты рейса. Используйте YYYY-MM-DD.'}, status=400)

            with transaction.atomic():
                flight_num_obj = get_object_or_404(FlightNumber, flights=flight_number_str)
                flight = get_object_or_404(InfTablo, flight=flight_num_obj, date1=flight_date)
                
                status_registration = get_object_or_404(Status, name_en='CHECK-IN')
                status_checkin_boarding = get_object_or_404(Status, name_en='CHECK-IN BOARDING')
                status_boarding = get_object_or_404(Status, name_en='BOARDING')
                status_checkin_closed = get_object_or_404(Status, name_en='CHECK-IN CLOSED') 

                # Удалена строка: if flight.stoika.exists(): flight.stoika.clear()
                # Это изменение сохраняет стойки после окончания регистрации.
                logger.info(f"Стойки для рейса {flight_number_str} на {flight_date_str} НЕ удалены по запросу пользователя.")


                if flight.status == status_registration:
                    flight.status = status_checkin_closed
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Регистрация' на 'Регистрация закрыта'.")
                elif flight.status == status_checkin_boarding:
                    flight.status = status_boarding
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Регистрация_Посадка' на 'Посадка'.")
                
                flight.save()

                return JsonResponse({'status': 'success', 'message': f'Регистрация рейса {flight_number_str} на {flight_date_str} завершена.'})
        except InfTablo.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Рейс {flight_number_str} на {flight_date_str} не найден.'}, status=404)
        except FlightNumber.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Номер рейса {flight_number_str} не найден в справочнике FlightNumber.'}, status=404)
        except Status.DoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': f'Ошибка: Отсутствует статус в таблице Status. Убедитесь, что существуют: "CHECK-IN", "CHECK-IN BOARDING", "BOARDING", "CHECK-IN CLOSED".'}, status=500)
        except Exception as e:
            logger.error(f"Ошибка при завершении регистрации для рейса {flight_number_str} на {flight_date_str}: {e}")
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
            flight_date_str = data.get('flight_date')

            if not flight_number_str or not flight_date_str:
                return JsonResponse({'status': 'error', 'message': 'Отсутствует номер рейса или дата рейса.'}, status=400)

            try:
                flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Неверный формат даты рейса. Используйте YYYY-MM-DD.'}, status=400)

            with transaction.atomic():
                flight_num_obj = get_object_or_404(FlightNumber, flights=flight_number_str)
                flight = get_object_or_404(InfTablo, flight=flight_num_obj, date1=flight_date)
                
                status_boarding = get_object_or_404(Status, name_en='BOARDING')
                status_checkin_boarding = get_object_or_404(Status, name_en='CHECK-IN BOARDING')
                status_asap = get_object_or_404(Status, name_en='ASAP') 
                status_registration = get_object_or_404(Status, name_en='CHECK-IN') 

                if flight.gate.exists():
                    flight.gate.clear()
                    logger.info(f"Все гейты удалены для рейса {flight_number_str} на {flight_date_str}.")

                if flight.status == status_boarding:
                    flight.status = status_asap
                    logger.info(f"Статус рейса {flight_number_str} на {flight_date_str} изменен с 'Посадка' на 'По готовности' (ASAP).")
                elif flight.status == status_checkin_boarding:
                    flight.status = status_registration 
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


def get_active_registrations_api(request, lang='en'):
    """
    Возвращает список рейсов, для которых в данный момент идет регистрация ('CHECK-IN' или 'CHECK-IN BOARDING').
    Используется для оповещения диспетчеров.
    """
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    
    # Ищем рейсы со статусами CHECK-IN или CHECK-IN BOARDING,
    # которые относятся к сегодняшнему или завтрашнему дню (по дате вылета)
    active_registration_flights = InfTablo.objects.filter(
        direction='dep', # Предполагаем, что регистрация касается вылетающих рейсов
        status__name_en__in=['CHECK-IN', 'CHECK-IN BOARDING'],
        date1__gte=today,
        date1__lte=tomorrow
    ).select_related('flight', 'destination', 'status').prefetch_related('stoika').order_by('date1', 'time1')

    data = []
    for item in active_registration_flights:
        # Сериализуем данные аналогично тому, как это делается для табло,
        # но можем опустить погоду, если она не нужна диспетчерам в этом конкретном списке.
        # Для простоты пока оставим, если serialize_flight ее может обрабатывать.
        
        # Передаем None для weather_data, так как для этого списка она, скорее всего, не нужна.
        # Если нужна, то нужно будет вызывать get_weather_data(item.destination.city_name_ru).
        serialized_flight = serialize_flight(item, lang, weather_data=None)
        data.append(serialized_flight)

    return JsonResponse({'active_registrations': data}, safe=False)

# Страница для лога нажатий
def update_log(request):
    log_entries = UpdateLog.objects.all().order_by('-timestamp')  # Получаем все записи и сортируем по времени
    return render(request, 'app/update_log.html', {'log_entries': log_entries})