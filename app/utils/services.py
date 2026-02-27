import requests
import time
from datetime import datetime, timedelta
from django.db import transaction
from django.db.utils import IntegrityError
from ..models import InfTablo, Airline, Cities, FlightNumber, Status, Stoiki, Gates
from decouple import config


class FlightAPIClient:
    API_URL = config('FLIGHT_API_URL')

    @staticmethod
    def fetch_flight_data(op_type, selected_date):
        """Запрашивает данные из API за указанную дату."""
        if op_type not in ("O", "P"):
            return {"error": "Некорректный тип рейсов."}

        params = {
            "Op": op_type,
            "DPV": selected_date,  # передаем дату в формате dd.mm.yy
            "format": "json"
        }

        try:
            response = requests.get(FlightAPIClient.API_URL, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return []

    @staticmethod
    def save_flights_to_db(op_type, selected_date):
        """Получает данные для заданной даты и записывает их в БД (`InfTablo`)."""
        
        all_flights = FlightAPIClient.fetch_flight_data(op_type, selected_date)
        
        if not all_flights:
            return {"error": f"Данных нет для {selected_date} или API недоступно."}

        new_flights = []
        updated_flights = []
        delayed_flights = []

        with transaction.atomic():
            for flight in all_flights:
                try:
                    airline_name = flight.get("AKNumber", "").strip() or "Неизвестно"

                    destination, _ = Cities.objects.update_or_create(
                        iata_code=flight.get("IATA", "").strip(),
                        city_name_ru=flight.get("Destination", "").strip(),
                        defaults={
                            "city_name_en": flight.get("DestinationEN", "").strip(),
                            "city_name_ky": flight.get("DestinationKG", "").strip()
                        }
                    )

                    flight_number, _ = FlightNumber.objects.update_or_create(
                        flights=flight.get("FlightNum", "").strip()
                    )

                    status_text = flight.get("Remark", "").strip()
                    status, _ = Status.objects.update_or_create(
                        name_ru=status_text,
                        defaults={
                            "name_en": flight.get("RemarkEN", "").strip(),
                            "name_ky": flight.get("RemarkKG", "").strip()
                        }
                    )

                    date1 = FlightAPIClient.parse_date(flight.get("DataPlan"))
                    time1 = FlightAPIClient.parse_time(flight.get("TimePlan"))
                    last_date = FlightAPIClient.parse_date(flight.get("DataFact"))
                    last_time = FlightAPIClient.parse_time(flight.get("TimeFact"))

                    # Проверяем, существует ли рейс с таким же номером и датой
                    existing_flight = InfTablo.objects.filter(
                        flight=flight_number,
                        date1=date1,
                        direction="dep" if op_type == "O" else "arr"
                    ).first()

                    flight_obj, created = InfTablo.objects.update_or_create(
                        flight=flight_number,
                        date1=date1,
                        direction="dep" if op_type == "O" else "arr",
                        defaults={
                            "time1": time1,
                            "airline": airline_name,
                            "destination": destination,
                            "last_date": last_date,
                            "last_time": last_time,
                            "status": status
                        }
                    )

                    if created:
                        new_flights.append(flight_obj)
                    else:
                        updated_flights.append(flight_obj)
                        # Если рейс был задержан, добавляем его в список задержанных
                        if existing_flight and existing_flight.status.name_ru == "ЗАДЕРЖАН":
                            delayed_flights.append(flight_obj.flight.flights)

                except IntegrityError as e:
                    print(f"❌ Ошибка при записи рейса {flight.get('FlightNum', '')}: {str(e)}")
                    continue
                except Exception as e:
                    print(f"❌ Неожиданная ошибка при записи рейса {flight.get('FlightNum', '')}: {str(e)}")
                    continue

        return {
            "new": len(new_flights),
            "updated": len(updated_flights),
            "delayed": delayed_flights,
            "updated_flights": [f.flight.flights for f in updated_flights]
        }

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

