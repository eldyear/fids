# scanner_app/views.py
import json
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import BarcodeScan
from app.models import InfTablo, FlightNumber, FlightsList, Cities, Status
from django.db.models import Count, Q
from datetime import datetime, timedelta, date, time
from django.utils import timezone

# Этот view будет отображать панель мониторинга, если она вам нужна как HTML-страница
# Если вы используете barcode.html напрямую с файловой системы или другого сервера,
# то этот view может быть не нужен для отображения, но важен для обработки POST запросов.
# from django.shortcuts import render
# def barcode_scanner_dashboard(request):
#     # Возможно, здесь будут отображаться последние сканирования или статистика
#     return render(request, 'scanner_app/dashboard.html') # Создайте этот шаблон, если он нужен

@csrf_exempt # Отключаем CSRF защиту для простоты в рамках примера. В продакшене используйте CSRF токены!
@require_POST # Убеждаемся, что принимаем только POST запросы
# @login_required(login_url='login_view') - отключено для доступа из scanner_gui.py
def save_barcode_scan(request):
    try:
        data = json.loads(request.body)

        raw_barcode = data.get('raw_barcode')
        parsed_data = data.get('parsed_data', {})
        is_duplicate = data.get('is_duplicate', False)

        # Извлекаем компоненты номера рейса из распарсенных данных
        carrier_code = parsed_data.get('carrier_code', '').strip()
        flight_number_part = parsed_data.get('flight_number', '').strip()

        # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ЗДЕСЬ: ФОРМИРУЕМ НОМЕР РЕЙСА ДЛЯ ПОИСКА В FIDS ---
        # Используем существующие модели: FlightNumber и InfTablo
        flight_instance = None
        full_flight_number_searched = None # Добавим для отладки в ответе
        if carrier_code and flight_number_part:
            try:
                # Умная нормализация номера рейса:
                # - Убираем ведущие нули для длинных номеров
                # - Пытаемся сохранить структуру 2 цифр если это короткий номер, но для FlightsList ищем точное совпадение
                
                # 1. Формируем "чистый" номер рейса (без нулей в начале числовой части, если она есть)
                # Например: "MN002" -> "MN", "002" -> "2"
                # Но "FlightsList" может содержать "MN02" или "MN2". 
                # Стратегия: Перебираем варианты (с 1 ведущим нулем, без нулей, как есть)
                
                flight_num_digits = ""
                if flight_number_part.isdigit():
                    flight_num_digits = flight_number_part.lstrip('0')
                
                # Варианты для проверки в базе
                potential_flight_numbers = []
                
                # Вариант 1: Как пришло (например "002")
                potential_flight_numbers.append(f"{carrier_code}{flight_number_part}")
                
                if flight_num_digits:
                     # Вариант 2: Без ведущих нулей (например "2")
                    potential_flight_numbers.append(f"{carrier_code}{flight_num_digits}")
                    # Вариант 3: С одним ведущим нулем, если цифра одна (например "02")
                    if len(flight_num_digits) == 1:
                        potential_flight_numbers.append(f"{carrier_code}0{flight_num_digits}")
                    # Вариант 4: С двумя ведущими нулями (редко, но бывает)
                    potential_flight_numbers.append(f"{carrier_code}00{flight_num_digits}")

                # Удаляем дубликаты сохраняя порядок
                potential_flight_numbers = list(dict.fromkeys(potential_flight_numbers))
                
                print(f"DEBUG: Варианты номера рейса для поиска: {potential_flight_numbers}")

                # Ищем в справочнике FlightsList
                flight_ref = None
                found_flight_number_str = None
                
                for f_num in potential_flight_numbers:
                    flight_ref = FlightsList.objects.filter(flight_number=f_num).first()
                    if flight_ref:
                        found_flight_number_str = f_num
                        full_flight_number_searched = f_num
                        print(f"DEBUG: Найдено совпадение в FlightsList: {flight_ref.flight_number}")
                        break
                
                flight_instance = None
                current_date = timezone.localdate()
                now_time = timezone.localtime().time()

                if flight_ref:
                    # Ищем ВСЕ подходящие рейсы в InfTablo на этот день
                    potential_flights = InfTablo.objects.filter(
                        flight__flights=flight_ref.flight_number,
                        date1=current_date
                    )
                    
                    if potential_flights.count() > 1:
                        best_flight = None
                        min_diff = None
                        for pf in potential_flights:
                            if pf.time1:
                                diff = abs((pf.time1.hour * 3600 + pf.time1.minute * 60) - 
                                           (now_time.hour * 3600 + now_time.minute * 60))
                                if min_diff is None or diff < min_diff:
                                    min_diff = diff
                                    best_flight = pf
                        flight_instance = best_flight
                    else:
                        flight_instance = potential_flights.first()

                    if not flight_instance:
                        # 1. Получаем/Создаем FlightNumber
                        flight_num_obj, created_fn = FlightNumber.objects.get_or_create(
                            flights=flight_ref.flight_number
                        )
                        
                        # 2. Получаем/Создаем Cities (Destination)
                        destination_obj = None
                        if flight_ref.destination_icao:
                            destination_obj = Cities.objects.filter(icao_code=flight_ref.destination_icao).first()
                        
                        if not destination_obj and flight_ref.destination_city:
                            destination_obj = Cities.objects.filter(city_name_ru__iexact=flight_ref.destination_city).first()
                            
                        if not destination_obj:
                             city_name = flight_ref.destination_city or "Unknown"
                             icao = flight_ref.destination_icao or "ZZZZ"
                             destination_obj = Cities.objects.create(
                                 city_name_ru=city_name,
                                 city_name_ky=city_name,
                                 city_name_en=city_name,
                                 iata_code="ZZZ",
                                 icao_code=icao
                             )

                        # 3. Определяем направление
                        direction_map = {"ПРИЛЕТ": "arr", "ВЫЛЕТ": "dep"}
                        direction_code = direction_map.get(flight_ref.direction.upper(), 'dep')

                        # 4. Создаем InfTablo
                        flight_instance = InfTablo.objects.create(
                            flight=flight_num_obj,
                            destination=destination_obj,
                            date1=current_date,
                            direction=direction_code,
                            airline=flight_ref.airline,
                            status=None
                        )

                else:
                    # Если не нашли в справочнике, пробуем прямой поиск в InfTablo
                    for f_num in potential_flight_numbers:
                        potential_flights = InfTablo.objects.filter(
                            flight__flights=f_num,
                            date1=current_date
                        )
                        
                        if potential_flights.exists():
                            if potential_flights.count() > 1:
                                best_flight = None
                                min_diff = None
                                for pf in potential_flights:
                                    if pf.time1:
                                        diff = abs((pf.time1.hour * 3600 + pf.time1.minute * 60) - 
                                                   (now_time.hour * 3600 + now_time.minute * 60))
                                        if min_diff is None or diff < min_diff:
                                            min_diff = diff
                                            best_flight = pf
                                flight_instance = best_flight
                            else:
                                flight_instance = potential_flights.first()
                            
                            if flight_instance:
                                full_flight_number_searched = f_num
                                break

            except Exception as e:
                flight_instance = None
        
        # --- ИЗМЕНЕНИЕ: НЕ ПРЕРЫВАЕМ СОХРАНЕНИЕ, ЕСЛИ РЕЙС НЕ НАЙДЕН ---
        if not flight_instance:
            flight_num_tag = f"{carrier_code}{flight_number_part}"
            print(f"WARNING: Рейс {flight_num_tag} не найден в FIDS, но сканирование будет сохранено.")
            # Мы больше не возвращаем ошибку, а продолжаем выполнение, чтобы сохранить данные
            # return JsonResponse({ ... }, status=404)

        # Проверяем дубликаты в базе данных Django
        passenger_name = parsed_data.get('passenger_name')
        if passenger_name and len(passenger_name) > 255: passenger_name = passenger_name[:255]
        
        pnr = parsed_data.get('PNR')
        if pnr and len(pnr) > 20: pnr = pnr[:20]
        
        seat_number = parsed_data.get('seat_number')
        if seat_number and len(seat_number) > 50: seat_number = seat_number[:50]
        
        # Определяем дату рейса для проверки дубликатов
        scan_flight_date = timezone.localdate() # По умолчанию сегодня в местном времени
        
        # 1. Пробуем получить готовую дату от клиента (если есть)
        if parsed_data.get('flight_date') and parsed_data.get('flight_date') != 'N/A':
            try:
                scan_flight_date = datetime.strptime(parsed_data.get('flight_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
        # 2. Если даты нет, но есть flight_date_info (Julian date из BCBP, например "137Y")
        elif parsed_data.get('flight_date_info') and parsed_data.get('flight_date_info') != 'N/A':
            julian_str = str(parsed_data.get('flight_date_info'))
            if julian_str[:3].isdigit():
                try:
                    day_of_year = int(julian_str[:3])
                    today = timezone.localdate()
                    # Вычисляем дату в текущем году
                    potential_date = date(today.year, 1, 1) + timedelta(days=day_of_year - 1)
                    # Корректировка года (если скан в конце года на рейс в начале следующего, или наоборот)
                    diff = (potential_date - today).days
                    if diff < -200: # Например, сегодня декабрь, а билет на январь
                        potential_date = date(today.year + 1, 1, 1) + timedelta(days=day_of_year - 1)
                    elif diff > 200: # Сегодня январь, а билет (зачем-то) за прошлый декабрь
                        potential_date = date(today.year - 1, 1, 1) + timedelta(days=day_of_year - 1)
                    scan_flight_date = potential_date
                except:
                    pass

        # Ищем существующие сканирования (Улучшенная логика)
        existing_scan = None
        
        if flight_instance:
            # Если рейс FIDS определен, дубликат - это пассажир с тем же именем на ЭТОМ ЖЕ самом рейсе
            existing_scan = BarcodeScan.objects.filter(
                passenger_name=passenger_name,
                flight=flight_instance
            ).first()
            pass
        else:
            # Если FIDS не нашел рейс, используем логику fallback только за сегодняшний день
            if raw_barcode:
                 existing_scan = BarcodeScan.objects.filter(
                    raw_barcode=raw_barcode,
                    timestamp__date=date.today()
                ).first()
    
            if not existing_scan and passenger_name and carrier_code and flight_number_part:
                existing_scan = BarcodeScan.objects.filter(
                    passenger_name=passenger_name,
                    carrier_code=carrier_code,
                    flight_number_str=flight_number_part,
                    flight_date=scan_flight_date,
                    timestamp__date=date.today()  # Только за сегодня
                ).first()
                pass
        
        # Если найден дубликат, помечаем новое сканирование как дубликат
        is_duplicate_in_db = existing_scan is not None
        
        # Проверка на подозрительность (Suspicious Check)
        is_suspicious = False
        suspicious_reason = ""
        
        if flight_instance:
            # 1. Рейс уже отправлен (Status or Fact Time)
            # Статус 5 - это обычно "Отправлен" или "Вылетел" (нужно уточнить ID статусов, но проверим по тексту)
            is_departed = False
            
            if flight_instance.status and "ОТПРАВЛЕН" in flight_instance.status.name_ru.upper():
                is_departed = True
            
            if flight_instance.last_time: # Факт вылета есть
                is_departed = True
                
            if is_departed:
                is_suspicious = True
                suspicious_reason = "Отсканировано после отправления рейса"

        # Helper to safely get and truncate
        def get_truncated(key, max_len):
            val = parsed_data.get(key)
            if val and len(str(val)) > max_len:
                return str(val)[:max_len]
            return val

        user_to_assign = request.user if request.user.is_authenticated else None
        raw_barcode = data.get('raw_barcode')
        
        # Интеграция с локальными пользователями клиента (scanner_advanced_gui2.py)
        client_user_data = data.get('client_user', {})
        if client_user_data:
            client_username = client_user_data.get('username') or client_user_data.get('full_name')
            if client_username:
                from django.contrib.auth.models import User
                # Используем безопасное имя пользователя без спецсимволов для поиска и создания
                safe_username = "".join(c for c in client_username if c.isalnum() or c in "._-")
                if safe_username:
                    # Пытаемся найти пользователя
                    found_user = User.objects.filter(username__iexact=safe_username).first()
                    if not found_user:
                        # Если нет - создаем автоматически
                        try:
                            found_user = User.objects.create_user(
                                username=safe_username,
                                first_name=client_user_data.get('full_name', ''),
                                password='defaultpassword123'
                            )
                        except Exception:
                            found_user = None
                
                if found_user:
                    user_to_assign = found_user

        # Создаем запись о сканировании
        barcode_scan = BarcodeScan.objects.create(
            user=user_to_assign,  # Привязываем к текущему пользователю или None если без авторизации
            raw_barcode=raw_barcode,
            scanner_prefix=get_truncated('scanner_prefix', 50),
            pax_type=get_truncated('pax_type', 50),
            passenger_name=passenger_name,
            pnr=pnr,
            origin_airport=get_truncated('origin_airport', 3),
            destination_airport=get_truncated('destination_airport', 3),
            carrier_code=get_truncated('carrier_code', 50), # Сохраняем код перевозчика из сканера
            flight_number_str=get_truncated('flight_number', 50), # Сохраняем номер рейса из сканера
            flight=flight_instance, # Ссылка на найденный объект Flight в FIDS (может быть None)
            flight_date_info=get_truncated('flight_date_info', 50),
            flight_date=scan_flight_date, # Сохраняем дату вылета (из баркода или сегодня)
            seat_number=seat_number,
            sequence_number=get_truncated('sequence_number', 50),
            additional_info_tail=get_truncated('additional_info_tail', 255),
            compartment_code=get_truncated('compartment_code', 50),
            is_duplicate=is_duplicate or is_duplicate_in_db,  # Объединяем флаги дубликатов
            is_suspicious=is_suspicious,
            suspicious_reason=suspicious_reason,
            parsed_data_json=parsed_data  # Сохраняем полные оригинальные данные от сканера
        )

        # Формируем сообщение о результате
        if is_duplicate_in_db:
            message = f'Дубликат! Пассажир {passenger_name} уже был отсканирован на рейсе {carrier_code}{flight_number_part} сегодня.'
        elif not flight_instance:
            message = f'Сканирование сохранено, но рейс {full_flight_number_searched or "неизвестный"} не найден в FIDS.'
        else:
            message = 'Данные сканирования успешно сохранены.'
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'scan_id': barcode_scan.id,
            'is_duplicate': is_duplicate_in_db,
            'flight_found': flight_instance is not None, # Теперь всегда True, если дошли до сюда
            'flight_number_searched': full_flight_number_searched, # Для отладки: какой номер использовался для поиска
            'flight_details': {
                'destination': flight_instance.destination.city_name_ru if flight_instance else None,
                'airline': flight_instance.airline if flight_instance else None,
                'status': flight_instance.status.name_ru if flight_instance and flight_instance.status else None,
                'date': flight_instance.date1.strftime('%Y-%m-%d') if flight_instance and flight_instance.date1 else None,
                'time': flight_instance.time1.strftime('%H:%M') if flight_instance and flight_instance.time1 else None,
            } if flight_instance else None
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Неверный формат JSON в запросе.'}, status=400)
    except Exception as e:
        print(f"Ошибка при сохранении сканирования: {e}") # Для отладки
        return JsonResponse({'status': 'error', 'message': f"Ошибка сервера: {str(e)}"}, status=500)
    
@login_required(login_url='login_view')
def get_barcode_scan(request):
    return render(request, 'scanner_app/barcode.html', {
        'current_user': request.user
    })

def login_view(request):
    """View для авторизации пользователей"""
    next_url = request.GET.get('next') or request.POST.get('next')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            
            # Если есть next_url, перенаправляем туда
            if next_url:
                return redirect(next_url)
            
            # Роль-основанное перенаправление
            if user.is_staff:
                # Администраторы идут на страницу отчетов
                return redirect('reports_view')
            else:
                # Обычные пользователи идут на сканер
                return redirect('get_barcode_scan')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль.')
    
    return render(request, 'scanner_app/login.html', {'next': next_url})

def logout_view(request):
    """View для выхода из системы"""
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('login_view')

@login_required(login_url='login_view')
def all_scans_view(request):
    """Отображение всех сканирований, сгруппированных по рейсам"""
    # Получаем параметры фильтра
    date_filter = request.GET.get('date', '')
    flight_filter = request.GET.get('flight', '')
    passenger_search = request.GET.get('passenger', '').strip()
    user_filter = request.GET.get('user', '').strip()
    # Базовый queryset - показываем все сканирования всем авторизованным пользователям
    scans = BarcodeScan.objects.all()
    # Фильтр по дате
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            # Используем осознанные (aware) datetime для точного поиска по часовому поясу
            start_dt = timezone.make_aware(datetime.combine(date_obj, time.min))
            end_dt = timezone.make_aware(datetime.combine(date_obj, time.max))
            scans = scans.filter(timestamp__range=(start_dt, end_dt))
        except ValueError:
            pass
    
    # Фильтр по пассажиру (улучшенный поиск)
    if passenger_search:
        print(f"DEBUG: Поиск по пассажиру: '{passenger_search}'")
        # Убираем пробелы и слэши из поискового запроса для гибкого поиска
        search_clean = passenger_search.replace(' ', '').replace('/', '')
        # Используем Q объекты для поиска по частичному совпадению
        from django.db.models import Q
        scans = scans.filter(
            Q(passenger_name__icontains=passenger_search) |  # Обычный поиск
            Q(passenger_name__iregex=r'.*' + '.*'.join(search_clean)) # Поиск без пробелов
        )
        print(f"DEBUG: Найдено сканирований после фильтра по пассажиру: {scans.count()}")
    
    # Фильтр по пользователю (только для администраторов)
    if user_filter and request.user.is_staff:
        print(f"DEBUG: Поиск по пользователю: '{user_filter}'")
        scans = scans.filter(user__username__icontains=user_filter)
        print(f"DEBUG: Найдено сканирований после фильтра по пользователю: {scans.count()}")
    
    # Группируем по рейсам
    flights_data = {}
    
    print(f"DEBUG: Всего сканирований для обработки: {scans.count()}")
    if passenger_search:
        print(f"DEBUG: Примеры passenger_name в результатах:")
        for scan in scans[:5]:
            print(f"  - '{scan.passenger_name}' (ID: {scan.id})")
    
    for scan in scans.order_by('-timestamp'):
        flight_key = f"{scan.carrier_code}{scan.flight_number_str}" if scan.carrier_code and scan.flight_number_str else "Unknown"
        
        if flight_key not in flights_data:
            flights_data[flight_key] = {
                'carrier_code': scan.carrier_code,
                'flight_number': scan.flight_number_str,
                'scans': [],
                'passenger_count': 0,
                'unique_passengers': set(),
                'flight_info': None
            }
        
        # Добавляем отображаемое имя пользователя прямо в Python, чтобы избежать
        # ошибки шаблона при scan.user == None
        if scan.user:
            scan.user_display = scan.user.first_name or scan.user.username
        else:
            scan.user_display = '-'
        flights_data[flight_key]['scans'].append(scan)
        flights_data[flight_key]['passenger_count'] += 1
        if scan.passenger_name:
            flights_data[flight_key]['unique_passengers'].add(scan.passenger_name)
        
        # Добавляем информацию о рейсе из FIDS
        if scan.flight and not flights_data[flight_key]['flight_info']:
            flights_data[flight_key]['flight_info'] = {
                'destination': scan.flight.destination.city_name_ru,
                'airline': scan.flight.airline,
                'status': scan.flight.status.name_ru if scan.flight.status else None,
                'date': scan.flight.date1,
                'time': scan.flight.time1,
            }
    
    # Конвертируем set в len для unique_passengers
    for flight_data in flights_data.values():
        flight_data['unique_passengers_count'] = len(flight_data['unique_passengers'])
        flight_data['unique_passengers'] = list(flight_data['unique_passengers'])
    
    # Фильтр по рейсу
    if flight_filter and flight_filter in flights_data:
        selected_flight = flights_data[flight_filter]
        context = {
            'flights': {flight_filter: selected_flight},
            'selected_flight': flight_filter,
            'show_passengers': True,
            'date_filter': date_filter,
            'passenger_search': passenger_search,
            'user_filter': user_filter,
            'current_user': request.user,
        }
    else:
        context = {
            'flights': flights_data,
            'selected_flight': None,
            'show_passengers': False,
            'date_filter': date_filter,
            'passenger_search': passenger_search,
            'user_filter': user_filter,
            'current_user': request.user,
        }
    
    return render(request, 'scanner_app/all_scans.html', context)

def get_all_scans_api(request):
    """API endpoint для получения всех сканирований в JSON формате"""
    scans = BarcodeScan.objects.all().order_by('-timestamp')
    
    scans_data = []
    for scan in scans:
        scan_data = {
            'id': scan.id,
            'timestamp': scan.timestamp.isoformat(),
            'raw_barcode': scan.raw_barcode,
            'scanner_prefix': scan.scanner_prefix,
            'pax_type': scan.pax_type,
            'passenger_name': scan.passenger_name,
            'pnr': scan.pnr,
            'origin_airport': scan.origin_airport,
            'destination_airport': scan.destination_airport,
            'carrier_code': scan.carrier_code,
            'flight_number_str': scan.flight_number_str,
            'flight_date_info': scan.flight_date_info,
            'seat_number': scan.seat_number,
            'sequence_number': scan.sequence_number,
            'additional_info_tail': scan.additional_info_tail,
            'compartment_code': scan.compartment_code,
            'is_duplicate': scan.is_duplicate,
            'flight_info': None
        }
        
        # Добавляем информацию о связанном рейсе
        if scan.flight:
            scan_data['flight_info'] = {
                'destination': scan.flight.destination.city_name_ru,
                'airline': scan.flight.airline,
                'status': scan.flight.status.name_ru if scan.flight.status else None,
                'date': scan.flight.date1.isoformat() if scan.flight.date1 else None,
                'time': scan.flight.time1.isoformat() if scan.flight.time1 else None,
                'flight_number': scan.flight.flight.flights if scan.flight.flight else None,
            }
        
        scans_data.append(scan_data)
    
    return JsonResponse({
        'status': 'success',
        'total_scans': len(scans_data),
        'unique_passengers': scans.values('passenger_name').distinct().count(),
        'unique_flights': scans.values('carrier_code', 'flight_number_str').distinct().count(),
        'scans': scans_data
    })

@login_required(login_url='login_view')
def reports_view(request):
    """Страница отчетов с расширенными фильтрами и экспортом"""
    # Получаем параметры фильтров
    # По умолчанию показываем только за сегодня, если даты не выбраны явно
    # Используем timezone.localdate() для учета TIME_ZONE из settings.py
    today_str = timezone.localdate().strftime('%Y-%m-%d')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Если параметры не переданы вообще (первая загрузка), ставим сегодня
    if start_date is None and end_date is None:
        start_date = today_str
        end_date = today_str
    
    # Если переданы пустые строки (сброс), можно оставить пустыми или тоже ставить сегодня
    # В данном случае, если пользователь нажал "Сбросить", он переходит по ссылке без параметров, так что сработает условие выше.
    # Но если он вручную стер дату, то придет пустая строка.
    # User request: "по умолчанию только данные отсортированные по текущей дате"
    # Let's ensure empty strings also default to today OR handle them as "All time"?
    # The user said "the more data the longer it loads", so defaulting to today seems safer for performance even on explicit clear?
    # Usually "Clear" means "All". But for performance, maybe "All" is bad.
    # Let's stick to: If GET params are missing (link click), default to Today.
    # If explicitly empty string (e.g. cleared input), let it be empty (All time, maybe with warning? or just All time).
    # But wait, standard form submission with empty date inputs sends empty strings.
    # So `request.GET.get('start_date')` will be `''` if form submitted with empty dates.
    # `request.GET.get('start_date')` will be `None` if accessed via link/menu.
    
    start_date = start_date if start_date is not None else today_str
    end_date = end_date if end_date is not None else today_str
    
    airline_filter = request.GET.get('airline', '').strip()
    flight_number_filter = request.GET.get('flight_number', '').strip()
    passenger_search = request.GET.get('passenger', '').strip()
    
    # Базовый queryset - показываем все сканирования всем авторизованным пользователям
    scans = BarcodeScan.objects.all()
    
    # Фильтр по диапазону дат
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            start_dt = timezone.make_aware(datetime.combine(start_date_obj, time.min))
            scans = scans.filter(timestamp__gte=start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            end_dt = timezone.make_aware(datetime.combine(end_date_obj, time.max))
            scans = scans.filter(timestamp__lte=end_dt)
        except ValueError:
            pass
    
    # Фильтр по авиакомпании
    if airline_filter:
        scans = scans.filter(carrier_code__icontains=airline_filter)
    
    # Фильтр по номеру рейса
    if flight_number_filter:
        scans = scans.filter(flight_number_str__icontains=flight_number_filter)
    
    # Поиск по пассажиру (улучшенный поиск)
    if passenger_search:
        # Убираем пробелы и слэши из поискового запроса для гибкого поиска
        search_clean = passenger_search.replace(' ', '').replace('/', '')
        # Используем Q объекты для поиска по частичному совпадению
        from django.db.models import Q
        scans = scans.filter(
            Q(passenger_name__icontains=passenger_search) |  # Обычный поиск
            Q(passenger_name__iregex=r'.*' + '.*'.join(search_clean)) # Поиск без пробелов
        )
    
    # Группируем по рейсам
    flights_data = {}
    
    for scan in scans.select_related('flight', 'flight__destination', 'flight__status', 'user').order_by('-timestamp'):
        flight_key = f"{scan.carrier_code}{scan.flight_number_str}" if scan.carrier_code and scan.flight_number_str else "Unknown"
        
        if flight_key not in flights_data:
            flights_data[flight_key] = {
                'carrier_code': scan.carrier_code,
                'flight_number': scan.flight_number_str,
                'scans': [],
                'passenger_count': 0,
                'unique_passengers': set(),
                'flight_info': None
            }
        
        # Добавляем отображаемое имя пользователя прямо в Python
        if scan.user:
            scan.user_display = scan.user.first_name or scan.user.username
        else:
            scan.user_display = '-'
        flights_data[flight_key]['scans'].append(scan)
        flights_data[flight_key]['passenger_count'] += 1
        if scan.passenger_name:
            flights_data[flight_key]['unique_passengers'].add(scan.passenger_name)
        
        # Добавляем информацию о рейсе из FIDS
        if scan.flight and not flights_data[flight_key]['flight_info']:
            flights_data[flight_key]['flight_info'] = {
                'destination': scan.flight.destination.city_name_ru if scan.flight.destination else None,
                'airline': scan.flight.airline,
                'status': scan.flight.status.name_ru if scan.flight.status else None,
                'date': scan.flight.date1,
                'time': scan.flight.time1,
            }
    
    # Конвертируем set в count для unique_passengers
    for flight_data in flights_data.values():
        flight_data['unique_passengers_count'] = len(flight_data['unique_passengers'])
        flight_data['unique_passengers'] = list(flight_data['unique_passengers'])
    
    # Получаем уникальные авиакомпании для dropdown
    airlines = BarcodeScan.objects.values_list('carrier_code', flat=True).distinct().order_by('carrier_code')
    airlines = [a for a in airlines if a]  # Убираем None значения
    
    context = {
        'flights': flights_data,
        'start_date': start_date,
        'end_date': end_date,
        'airline_filter': airline_filter,
        'flight_number_filter': flight_number_filter,
        'passenger_search': passenger_search,
        'airlines': airlines,
        'current_user': request.user,
        'total_scans': sum(f['passenger_count'] for f in flights_data.values()),
        'total_flights': len(flights_data),
    }
    
    return render(request, 'scanner_app/reports.html', context)

@login_required(login_url='login_view')
def export_to_excel(request):
    """Экспорт отчета в Excel с учетом фильтров"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from django.http import HttpResponse
        
        # Получаем те же фильтры, что и в reports_view
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        airline_filter = request.GET.get('airline', '').strip()
        flight_number_filter = request.GET.get('flight_number', '').strip()
        passenger_search = request.GET.get('passenger', '').strip()
        
        # Применяем те же фильтры
        scans = BarcodeScan.objects.all()
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                scans = scans.filter(timestamp__date__gte=start_date_obj)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                scans = scans.filter(timestamp__date__lte=end_date_obj)
            except ValueError:
                pass
        
        if airline_filter:
            scans = scans.filter(carrier_code__icontains=airline_filter)
        
        if flight_number_filter:
            scans = scans.filter(flight_number_str__icontains=flight_number_filter)
        
        if passenger_search:
            scans = scans.filter(passenger_name__icontains=passenger_search)
        
        # Создаем Excel файл
        wb = Workbook()
        ws = wb.active
        ws.title = "Отчет по сканированиям"
        
        # Стили
        header_font = Font(bold=True, size=12)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        # Заголовки
        headers = ['№', 'Дата/Время', 'Рейс', 'Авиакомпания', 'Пассажир', 'PNR', 'Место', 'Направление', 'Пользователь']
        ws.append(headers)
        
        # Форматируем заголовки
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # Добавляем данные
        for idx, scan in enumerate(scans.select_related('flight', 'user').order_by('-timestamp'), start=1):
            destination = scan.flight.destination.city_name_ru if scan.flight and scan.flight.destination else scan.destination_airport or '-'
            ws.append([
                idx,
                scan.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                f"{scan.carrier_code}{scan.flight_number_str}" if scan.carrier_code and scan.flight_number_str else '-',
                scan.carrier_code or '-',
                scan.passenger_name or '-',
                scan.pnr or '-',
                scan.seat_number or '-',
                destination,
                scan.user.username if scan.user else '-'
            ])
        
        # Автоматическая ширина колонок
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Создаем HTTP response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        
        wb.save(response)
        return response
        
    except ImportError:
        messages.error(request, 'Библиотека openpyxl не установлена. Установите: pip install openpyxl')
        return redirect('reports_view')
    except Exception as e:
        messages.error(request, f'Ошибка при создании Excel файла: {str(e)}')
        return redirect('reports_view')

@login_required(login_url='login_view')
def export_to_pdf(request):
    """Экспорт отчета в PDF с учетом фильтров"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from django.http import HttpResponse
        import io
        
        # Получаем те же фильтры
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        airline_filter = request.GET.get('airline', '').strip()
        flight_number_filter = request.GET.get('flight_number', '').strip()
        passenger_search = request.GET.get('passenger', '').strip()
        
        # Базовый queryset - показываем все сканирования всем авторизованным пользователям
        scans = BarcodeScan.objects.all()
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                scans = scans.filter(timestamp__date__gte=start_date_obj)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                scans = scans.filter(timestamp__date__lte=end_date_obj)
            except ValueError:
                pass
        
        if airline_filter:
            scans = scans.filter(carrier_code__icontains=airline_filter)
        
        if flight_number_filter:
            scans = scans.filter(flight_number_str__icontains=flight_number_filter)
        
        if passenger_search:
            scans = scans.filter(passenger_name__icontains=passenger_search)
        
        # Создаем PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        # Регистрируем шрифт с поддержкой кириллицы
        try:
            # Пытаемся использовать DejaVuSans (обычно доступен в Linux)
            pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
            font_name = 'DejaVuSans'
            font_name_bold = 'DejaVuSans-Bold'
        except:
            # Если DejaVuSans не найден, пробуем Liberation Sans
            try:
                pdfmetrics.registerFont(TTFont('LiberationSans', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'))
                pdfmetrics.registerFont(TTFont('LiberationSans-Bold', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'))
                font_name = 'LiberationSans'
                font_name_bold = 'LiberationSans-Bold'
            except:
                # Fallback на Helvetica (не поддерживает кириллицу)
                font_name = 'Helvetica'
                font_name_bold = 'Helvetica-Bold'
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            fontName=font_name_bold,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=20,
            alignment=1  # Center
        )
        
        filter_style = ParagraphStyle(
            'FilterInfo',
            parent=styles['Normal'],
            fontSize=10,
            fontName=font_name,
            textColor=colors.HexColor('#333333'),
            spaceAfter=5,
            leftIndent=20
        )
        
        # Заголовок
        title = Paragraph("Отчет по сканированиям пассажиров", title_style)
        elements.append(title)
        
        # Информация о фильтрах
        filter_info = []
        if start_date or end_date or airline_filter or flight_number_filter or passenger_search:
            filter_title = Paragraph("<b>Примененные фильтры:</b>", filter_style)
            elements.append(filter_title)
            
            if start_date and end_date:
                filter_info.append(f"• Период: с {start_date} по {end_date}")
            elif start_date:
                filter_info.append(f"• Дата начала: {start_date}")
            elif end_date:
                filter_info.append(f"• Дата окончания: {end_date}")
            
            if airline_filter:
                filter_info.append(f"• Авиакомпания: {airline_filter}")
            
            if flight_number_filter:
                filter_info.append(f"• Номер рейса: {flight_number_filter}")
            
            if passenger_search:
                filter_info.append(f"• Поиск пассажира: {passenger_search}")
            
            for info in filter_info:
                elements.append(Paragraph(info, filter_style))
            
            elements.append(Spacer(1, 0.2*inch))
        else:
            elements.append(Paragraph("<i>Фильтры не применены (все данные)</i>", filter_style))
            elements.append(Spacer(1, 0.2*inch))
        
        # Статистика
        total_scans = scans.count()
        stats_style = ParagraphStyle(
            'Stats',
            parent=styles['Normal'],
            fontSize=10,
            fontName=font_name,
            textColor=colors.HexColor('#666666'),
            alignment=1,
            spaceAfter=15
        )
        stats_text = f"Всего записей: {total_scans} | Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        elements.append(Paragraph(stats_text, stats_style))
        
        # Таблица данных (компактная для A4)
        data = [['№', 'Дата/Время', 'Рейс', 'Пассажир', 'PNR', 'Место', 'Направление']]
        
        for idx, scan in enumerate(scans.select_related('flight').order_by('-timestamp'), start=1):
            destination = scan.flight.destination.city_name_ru if scan.flight and scan.flight.destination else scan.destination_airport or '-'
            # Сокращаем имя пассажира если слишком длинное
            passenger_name = scan.passenger_name or '-'
            if len(passenger_name) > 25:
                passenger_name = passenger_name[:22] + '...'
            
            # Формируем дату и время рейса
            flight_dt_str = "-"
            if scan.flight:
                # Берем данные из FIDS (плановая дата и время)
                f_date = scan.flight.date1.strftime('%d.%m.%Y') if scan.flight.date1 else "-"
                f_time = scan.flight.time1.strftime('%H:%M') if scan.flight.time1 else ""
                flight_dt_str = f"{f_date}\n{f_time}".strip()
            elif scan.flight_date:
                # Если связи с FIDS нет, берем расшифрованную дату из билета
                flight_dt_str = scan.flight_date.strftime('%d.%m.%Y')
            
            data.append([
                str(idx),
                flight_dt_str,
                f"{scan.carrier_code}{scan.flight_number_str}" if scan.carrier_code and scan.flight_number_str else '-',
                passenger_name,
                scan.pnr or '-',
                scan.seat_number or '-',
                destination[:15] if destination and len(destination) > 15 else destination or '-'
            ])
        
        # Создаем таблицу с оптимальными размерами для A4
        col_widths = [0.6*inch, 1.1*inch, 0.8*inch, 2.2*inch, 0.9*inch, 0.7*inch, 1.5*inch]
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Заголовок
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Данные
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(table)
        
        # Генерируем PDF
        doc.build(elements)
        
        # Создаем HTTP response
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        
        return response
        
    except ImportError:
        messages.error(request, 'Библиотека reportlab не установлена. Установите: pip install reportlab')
        return redirect('reports_view')
    except Exception as e:
        messages.error(request, f'Ошибка при создании PDF файла: {str(e)}')
        return redirect('reports_view')

@csrf_exempt
def refresh_fids_data(request):
    """
    Эндпоинт для синхронизации данных из fids_full.json.
    Вызывается Go-приложением при обновлении данных.
    """
    api_url = "http://31.192.250.185/api/fids_full.json"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        flights_data = response.json()
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Failed to fetch API: {e}'}, status=500)
    
    updated_count = 0
    created_count = 0
    
    for item in flights_data:
        try:
            # Парсим основные данные
            direction = 'dep' if item.get('dir') == 'O' else 'arr'
            carrier = item.get('al', '')
            full_flt = item.get('flt', '')
            
            sch_d_str = item.get('sch_d')
            sch_t_str = item.get('sch_t', '').replace('.', ':')
            
            if not sch_d_str or not sch_t_str:
                continue
                
            sch_date = datetime.strptime(sch_d_str, '%Y-%m-%d').date()
            sch_time = datetime.strptime(sch_t_str, '%H:%M').time()
            
            # 1. Город (Destination)
            dest_data = item.get('dest', {})
            city_name_ru = dest_data.get('ru', 'Unknown')
            city_obj, _ = Cities.objects.get_or_create(
                city_name_ru=city_name_ru,
                defaults={
                    'city_name_en': dest_data.get('en', city_name_ru),
                    'city_name_ky': dest_data.get('ky', city_name_ru),
                }
            )
            
            # 2. Статус
            status_obj = None
            status_data = item.get('status', {})
            status_name_ru = status_data.get('ru')
            if status_name_ru and status_name_ru.strip():
                status_obj, _ = Status.objects.get_or_create(
                    name_ru=status_name_ru.strip(),
                    defaults={
                        'name_en': status_data.get('en', status_name_ru),
                        'name_ky': status_data.get('ky', status_name_ru),
                    }
                )
            
            # 3. Номер рейса
            flight_num_obj, _ = FlightNumber.objects.get_or_create(flights=full_flt)
            
            # 4. Ищем или создаем запись в InfTablo
            inf_tablo_item, created = InfTablo.objects.get_or_create(
                flight=flight_num_obj,
                date1=sch_date,
                time1=sch_time,
                defaults={
                    'direction': direction,
                    'airline': carrier,
                    'destination': city_obj,
                    'status': status_obj,
                }
            )
            
            if not created:
                inf_tablo_item.status = status_obj
                last_t_str = item.get('act_t') or item.get('est_t')
                if last_t_str:
                    try:
                        last_t_str = last_t_str.replace('.', ':')
                        inf_tablo_item.last_time = datetime.strptime(last_t_str, '%H:%M').time()
                        inf_tablo_item.last_date = sch_date
                    except:
                        pass
                inf_tablo_item.save()
                updated_count += 1
            else:
                created_count += 1
                
        except Exception:
            continue
            
    return JsonResponse({
        'status': 'success', 
        'created': created_count, 
        'updated': updated_count,
        'total_processed': len(flights_data)
    })