import requests
import time
from datetime import datetime, timedelta
from django.db import transaction
from django.db.utils import IntegrityError
from ..models import InfTablo, Airline, Cities, FlightNumber, Status, Stoiki, Gates


class FlightAPIClient:
    API_URL = "http://199.1.1.2:1972/csp/adp/japi.csp"

    @staticmethod
    def fetch_flight_data(op_type, selected_date):
        # ... (ваш существующий код без изменений)
        if op_type not in ("O", "P"):
            return {"error": "Некорректный тип рейсов."}

        params = {
            "Op": op_type,
            "DPV": selected_date,
            "format": "json"
        }

        try:
            response = requests.get(FlightAPIClient.API_URL, params=params, timeout=10) # Увеличил таймаут на всякий случай
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Ошибка запроса к API: {e}")
            return []


    @staticmethod
    def save_flights_to_db(op_type, selected_date):
        """
        Получает данные для заданной даты и записывает их в БД (`InfTablo`).
        Возвращает:
        - {"confirm_flights": [...]} если есть рейсы на подтверждение
        - {"success": "..."} если все успешно сохранено/обновлено без подтверждений
        - {"error": "..."} если произошла ошибка
        """
        
        all_flights = FlightAPIClient.fetch_flight_data(op_type, selected_date)
        
        if not all_flights:
            return {"error": f"Данных нет для {selected_date} или API недоступно."}

        new_flights_count = 0
        updated_flights_count = 0
        flights_to_confirm = [] # Список для рейсов, требующих подтверждения

        with transaction.atomic():
            for flight_data in all_flights:
                try:
                    airline_name = flight_data.get("AKNumber", "").strip() or "Неизвестно"

                    destination, _ = Cities.objects.update_or_create(
                        iata_code=flight_data.get("IATA", "").strip(),
                        city_name_ru=flight_data.get("Destination", "").strip(),
                        defaults={
                            "city_name_en": flight_data.get("DestinationEN", "").strip(),
                            "city_name_ky": flight_data.get("DestinationKG", "").strip()
                        }
                    )

                    flight_number_str = flight_data.get("FlightNum", "").strip()
                    if not flight_number_str: # Проверка на пустой номер рейса
                        print(f"Предупреждение: Пропущен рейс с пустым номером. Данные: {flight_data}")
                        continue

                    flight_number, _ = FlightNumber.objects.update_or_create(
                        flights=flight_number_str
                    )

                    status_text = flight_data.get("Remark", "").strip()
                    status, _ = Status.objects.update_or_create(
                        name_ru=status_text,
                        defaults={
                            "name_en": flight_data.get("RemarkEN", "").strip(),
                            "name_ky": flight_data.get("RemarkKG", "").strip()
                        }
                    )

                    date1 = FlightAPIClient.parse_date(flight_data.get("DataPlan"))
                    time1 = FlightAPIClient.parse_time(flight_data.get("TimePlan"))
                    last_date = FlightAPIClient.parse_date(flight_data.get("DataFact"))
                    last_time = FlightAPIClient.parse_time(flight_data.get("TimeFact"))

                    if not date1 or not time1: # Проверка на корректность даты/времени
                         print(f"Предупреждение: Пропущен рейс {flight_number_str} из-за некорректной даты/времени. Данные: {flight_data}")
                         continue

                    existing_flight = InfTablo.objects.filter(
                        flight=flight_number,
                        date1=date1,
                        direction="dep" if op_type == "O" else "arr"
                    ).first()

                    # Ключевое изменение: если рейс существует и новый статус "ЗАДЕРЖАН"
                    if existing_flight and status_text == "ЗАДЕРЖАН":
                        flights_to_confirm.append({
                            "flight_id": existing_flight.id, # ID существующей записи InfTablo
                            "flight_num": flight_number.flights,
                            "current_status": existing_flight.status.name_ru if existing_flight.status else "Неизвестно",
                            "new_status_text": status_text,
                            "new_time1": time1.isoformat() if time1 else None, # Для передачи в JS
                            "new_last_time": last_time.isoformat() if last_time else None, # Для передачи в JS
                            "op_type": op_type # Направление рейса для использования в API
                        })
                        continue # Пропускаем обновление InfTablo на этом шаге, ждем подтверждения

                    # Если рейса нет или статус не "ЗАДЕРЖАН", или "ЗАДЕРЖАН" уже неактуален (статус изменился)
                    flight_obj, created = InfTablo.objects.update_or_create(
                        flight=flight_number,
                        date1=date1,
                        direction="dep" if op_type == "O" else "arr",
                        defaults={
                            "time1": time1,
                            # Важно: если airline - это строка, как у вас, то так и оставляем.
                            # Если должна быть ForeignKey на Airline, то нужно найти/создать объект Airline.
                            "airline": airline_name, 
                            "destination": destination,
                            "last_date": last_date,
                            "last_time": last_time,
                            "status": status
                        }
                    )
                    if created:
                        new_flights_count += 1
                        print(f"➕ Добавлен новый рейс {flight_number.flights}.")
                    else:
                        updated_flights_count += 1
                        print(f"✅ Обновлен рейс {flight_number.flights}.")

                except IntegrityError as e:
                    print(f"❌ Ошибка целостности при записи рейса {flight_data.get('FlightNum', '')}: {str(e)}")
                    continue
                except Exception as e:
                    print(f"❌ Неожиданная ошибка при записи рейса {flight_data.get('FlightNum', '')}: {str(e)}")
                    continue

        if flights_to_confirm:
            return {"confirm_flights": flights_to_confirm, "initial_message": f"Сохранено {new_flights_count} новых и обновлено {updated_flights_count} рейсов без подтверждения."}
        else:
            return {"success": f"✅ Сохранено {new_flights_count} новых и обновлено {updated_flights_count} рейсов."}

    @staticmethod
    def apply_confirmed_delay(flight_id, new_status_text, new_time1_str, new_last_time_str):
        """
        Применяет подтвержденную задержку к рейсу.
        """
        try:
            flight_obj = InfTablo.objects.get(id=flight_id)
            
            # Находим или создаем объект статуса "ЗАДЕРЖАН"
            delayed_status, _ = Status.objects.get_or_create(
                name_ru=new_status_text, 
                defaults={"name_en": "DELAYED", "name_ky": "КЕЧИКТИРИЛГЕН"}
            )
            flight_obj.status = delayed_status
            
            # Преобразуем строки времени обратно в объекты time
            if new_time1_str:
                flight_obj.time1 = datetime.strptime(new_time1_str, "%H:%M:%S").time()
            if new_last_time_str:
                flight_obj.last_time = datetime.strptime(new_last_time_str, "%H:%M:%S").time()
            
            flight_obj.save()
            return {"success": f"Рейс {flight_obj.flight.flights} успешно обновлен как '{new_status_text}'."}
        except InfTablo.DoesNotExist:
            return {"error": "Рейс не найден для обновления."}
        except Exception as e:
            return {"error": f"Ошибка при применении задержки для рейса {flight_id}: {str(e)}"}



    @staticmethod
    def parse_date(date_str):
        """Преобразует строку даты в объект `datetime.date`."""
        try:
            return datetime.strptime(date_str, "%d.%m.%y").date()
        except (ValueError, TypeError):
            return None  

    @staticmethod
    def parse_time(time_str):
        """Преобразует строку времени в объект `datetime.time`."""
        try:
            return datetime.strptime(time_str.replace(".", ":"), "%H:%M").time()
        except (ValueError, TypeError, AttributeError):
            return None

