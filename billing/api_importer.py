import requests
import json
from datetime import datetime, timedelta
from django.db import transaction

from .models import Flight, Airport, Airline, ServiceType

MUMPS_API_URL = "http://31.192.250.185:1972/csp/adp/japiutcspp2.csp"
SERVICES_API_URL = "http://31.192.250.185:1972/csp/adp/uslugi.csp"

def import_flights_from_api(target_date_str=None, from_time_str=None, to_time_str=None):
    """
    Извлекает данные о рейсах из MUMPS API, сохраняет/обновляет их,
    связывает по ID и помечает устаревшие рейсы как неактивные.
    """
    print(f"--- Начало импорта рейсов для даты: {target_date_str or 'текущая'} ---")

    params = {'format': 'json'}
    if target_date_str:
        try:
            dt_obj = datetime.strptime(target_date_str, '%Y-%m-%d')
            mumps_date_str = dt_obj.strftime('%d.%m.%y')
            params['Dn'] = mumps_date_str
        except ValueError:
            return False, "Ошибка: Неверный формат даты. Используйте ГГГГ-ММ-ДД."
    if from_time_str:
        params['Ft'] = from_time_str
    if to_time_str:
        params['Tt'] = to_time_str

    try:
        print(f"Отправка запроса на API с параметрами: {params}")
        
        response = requests.get(MUMPS_API_URL, params=params, timeout=30)
        response.raise_for_status()

        try:
            api_data = json.loads(response.text)
        except json.JSONDecodeError:
            print(f"Ошибка декодирования JSON: Получен невалидный JSON: {response.text[:200]}...")
            return False, "Ошибка: API вернул невалидные данные."

        if not isinstance(api_data, list):
            print(f"Ошибка: API вернул данные не в формате списка: {response.text[:200]}...")
            return False, "Ошибка: API вернул данные не в ожидаемом формате списка."

        if not api_data:
            print("API вернул пустой список рейсов.")
            # Если API пустой, помечаем все рейсы за эту дату как неактивные.
            if target_date_str:
                mumps_epoch_date = datetime(1840, 12, 31).date()
                flight_date = mumps_epoch_date + timedelta(days=int(item['Date']))
                Flight.objects.filter(date=flight_date, is_active=True).update(is_active=False)
            return True, "Данные обновлены. Нет рейсов для указанных параметров."

        imported_count = 0
        updated_count = 0
        
        imported_flights = {}
        
        # --- Этап 1: Импорт или обновление всех рейсов ---
        print("\n--- Этап 1: Импорт или обновление данных о рейсах ---")
        current_api_ids = []
        
        with transaction.atomic():
            for item in api_data:
                try:
                    mumps_epoch_date = datetime(1840, 12, 31).date()
                    flight_date = mumps_epoch_date + timedelta(days=int(item['Date']))

                    dep_airport_code = item.get('DepAirportCode')
                    arr_airport_code = item.get('ArrAirportCode')
                    airline_code = item.get('Airline')
                    current_flight_id = item.get('CurrentFlightId')

                    if not dep_airport_code or not arr_airport_code or not airline_code or not current_flight_id:
                        print(f"Пропущена запись из-за отсутствия необходимого кода (аэропорта, авиакомпании или ID): {item}")
                        continue
                        
                    current_api_ids.append(current_flight_id)

                    dep_airport_obj, _ = Airport.objects.get_or_create(
                        code=dep_airport_code,
                        defaults={'name': item.get('DepAirport', dep_airport_code)}
                    )
                    arr_airport_obj, _ = Airport.objects.get_or_create(
                        code=arr_airport_code,
                        defaults={'name': item.get('ArrAirport', arr_airport_code)}
                    )
                    
                    airline_obj, _ = Airline.objects.get_or_create(
                        code=airline_code,
                        defaults={'name': airline_code}
                    )
                    
                    paired_flight_id = item.get('PairedFlightId')
                    print(f"Processing flight ID: {current_flight_id}. FactDate from API: {item.get('FactDate')}")

                    # Используем 'current_flight_id' в качестве единственного уникального ключа
                    flight_defaults = {
                        'date': flight_date,
                        'region': item['Region'],
                        'direction': item['Direction'],
                        'flight_num': item['FlightNum'],
                        'time': item.get('TimePlan'), # time теперь часть defaults
                        'date_plan': item.get('DatePlan'),
                        'date_fact': item.get('FactDate'),
                        'airline': airline_obj,
                        'aircraft_type': item.get('AircraftType'),
                        'board_num': item.get('BoardNum'),
                        'dep_airport': dep_airport_obj,
                        'arr_airport': arr_airport_obj,
                        'estimated_time': item.get('TimeEst'),
                        'actual_time': item.get('FactTime'),
                        'codeshare': item.get('CodeShare'),
                        'stand': item.get('Stand'),
                        'checkin': item.get('Checkin'),
                        'gate': item.get('Gate'),
                        'tech_card': item.get('TechCard'),
                        'board_base': item.get('BoardBase'),
                        'paired_flight_id': paired_flight_id, 
                        'is_active': True, # Важно: помечаем рейс как активный
                    }

                    flight, created = Flight.objects.update_or_create(
                        current_flight_id=current_flight_id,
                        defaults=flight_defaults
                    )
                    
                    imported_flights[current_flight_id] = flight

                    if created:
                        imported_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    print(f"Ошибка обработки записи: {item}. Ошибка: {e}")
                    continue
        
        print(f"Этап 1 завершен. Импортировано: {imported_count}, обновлено: {updated_count}.")
        
        # --- Этап 2: Пометка устаревших рейсов как неактивных ---
        print("\n--- Этап 2: Пометка устаревших рейсов как неактивных ---")
        if target_date_str:
            # Преобразование строки даты в объект datetime.date
            mumps_epoch_date = datetime(1840, 12, 31).date()
            flight_date = mumps_epoch_date + timedelta(days=int(api_data[0]['Date']))
            
            # Находим и помечаем как неактивные все рейсы за эту дату,
            # которых нет в текущем ответе API
            stale_flights = Flight.objects.filter(
                date=flight_date,
                is_active=True
            ).exclude(current_flight_id__in=current_api_ids)
            
            inactive_count = stale_flights.update(is_active=False)
            print(f"Обновлено неактивных рейсов: {inactive_count}.")
        
        # --- Этап 3: Связывание рейсов по ID ---
        print("\n--- Этап 3: Связывание рейсов по ID ---")
        linked_pairs_count = 0
        linked_ids_processed = set()
        
        with transaction.atomic():
            for current_id, flight_obj in imported_flights.items():
                paired_id = flight_obj.paired_flight_id
                
                if paired_id and paired_id in imported_flights and current_id not in linked_ids_processed:
                    paired_flight_obj = imported_flights[paired_id]
                    
                    if flight_obj.linked_flight != paired_flight_obj or paired_flight_obj.linked_flight != flight_obj:
                        flight_obj.linked_flight = paired_flight_obj
                        paired_flight_obj.linked_flight = flight_obj
                        flight_obj.save(update_fields=['linked_flight'])
                        paired_flight_obj.save(update_fields=['linked_flight'])
                        linked_pairs_count += 1
                        linked_ids_processed.add(current_id)
                        linked_ids_processed.add(paired_id)

        print(f"Этап 3 завершен. Связано пар рейсов: {linked_pairs_count}.")
        
        return True, f"Данные успешно обновлены. Импортировано: {imported_count}, обновлено: {updated_count}, неактивных: {inactive_count}, связано пар рейсов: {linked_pairs_count}."

    except requests.exceptions.Timeout:
        return False, "Ошибка: Время ожидания ответа от API истекло."
    except requests.exceptions.RequestException as e:
        return False, f"Ошибка при запросе к API: {e}"
    except Exception as e:
        return False, f"Произошла непредвиденная ошибка: {e}"
def import_service_types_from_api():
    """
    Извлекает типы услуг из API и сохраняет/обновляет их в базе данных.
    """
    print(f"--- Начало импорта типов услуг из {SERVICES_API_URL} ---")
    
    try:
        response = requests.get(SERVICES_API_URL, timeout=30)
        response.raise_for_status()
        
        try:
            api_data = response.json()
        except json.JSONDecodeError:
            print(f"Ошибка декодирования JSON: {response.text[:200]}...")
            return False, "API вернул невалидный JSON."

        if not isinstance(api_data, list):
            return False, "API вернул данные не в формате списка."

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for item in api_data:
                code = item.get('id')
                name = item.get('description')

                if not code or not name:
                    continue

                obj, created = ServiceType.objects.update_or_create(
                    code=code,
                    defaults={'name': name}
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        return True, f"Импорт услуг завершен: создано {created_count}, обновлено {updated_count}."

    except requests.exceptions.RequestException as e:
        return False, f"Ошибка при запросе к API: {e}"
    except Exception as e:
        return False, f"Произошла непредвиденная ошибка: {e}"
