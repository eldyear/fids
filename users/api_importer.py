import requests
from datetime import datetime
from django.db import transaction
from django.conf import settings
from decouple import config

from app.models import InfTablo, Airline, Cities, FlightNumber, Status

# Use the URL from settings or config, fallback to the one seen in previous files if needed.
# services.py used config('FLIGHT_API_URL').
# We'll try to get it from settings or use the hardcoded one if missing.
API_URL = config('FLIGHT_API_URL', default="https://api.example.com/flights")

def fetch_flight_data(op_type, selected_date):
    """
    Fetches flight data from API for a specific date and operation type.
    op_type: "O" (Departure) or "P" (Arrival)
    selected_date: "dd.mm.yy"
    """
    params = {
        "Op": op_type,
        "DPV": selected_date,
        "format": "json"
    }
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d.%m.%y").date()
    except (ValueError, TypeError):
        return None

def parse_time(time_str):
    try:
        return datetime.strptime(time_str.replace(".", ":"), "%H:%M").time()
    except (ValueError, TypeError, AttributeError):
        return None

def import_flights_from_api(target_date_str=None):
    """
    Imports flights using the logic from app/utils/services.py.
    Imports both Departures (O) and Arrivals (P).
    """
    if not target_date_str:
        target_date_str = datetime.now().strftime('%Y-%m-%d')

    # Convert YYYY-MM-DD to dd.mm.yy for API
    try:
        dt_obj = datetime.strptime(target_date_str, '%Y-%m-%d')
        api_date_str = dt_obj.strftime('%d.%m.%y')
    except ValueError:
        return False, "Invalid date format."

    print(f"--- Importing for {api_date_str} ---")

    total_new = 0
    total_updated = 0

    with transaction.atomic():
        for op_type in ["O", "P"]: # O = Departure, P = Arrival
            direction = "dep" if op_type == "O" else "arr"
            flights_data = fetch_flight_data(op_type, api_date_str)

            if not flights_data:
                continue

            for flight in flights_data:
                try:
                    # Logic from services.py
                    airline_name = flight.get("AKNumber", "").strip() or "Неизвестно"

                    # City/Destination
                    destination, _ = Cities.objects.update_or_create(
                        iata_code=flight.get("IATA", "").strip(),
                        city_name_ru=flight.get("Destination", "").strip(),
                        defaults={
                            "city_name_en": flight.get("DestinationEN", "").strip(),
                            "city_name_ky": flight.get("DestinationKG", "").strip()
                        }
                    )

                    # Flight Number
                    flight_number, _ = FlightNumber.objects.update_or_create(
                        flights=flight.get("FlightNum", "").strip()
                    )

                    # Status
                    status_text = flight.get("Remark", "").strip()
                    status, _ = Status.objects.update_or_create(
                        name_ru=status_text,
                        defaults={
                            "name_en": flight.get("RemarkEN", "").strip(),
                            "name_ky": flight.get("RemarkKG", "").strip()
                        }
                    )

                    date1 = parse_date(flight.get("DataPlan"))
                    time1 = parse_time(flight.get("TimePlan"))
                    last_date = parse_date(flight.get("DataFact"))
                    last_time = parse_time(flight.get("TimeFact"))

                    # Update or Create InfTablo
                    # Note: services.py used (flight, date1, direction) as unique key logic
                    flight_obj, created = InfTablo.objects.update_or_create(
                        flight=flight_number,
                        date1=date1,
                        direction=direction,
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
                        total_new += 1
                    else:
                        total_updated += 1

                except Exception as e:
                    print(f"Error processing flight {flight}: {e}")
                    continue

    return True, f"Import complete. New: {total_new}, Updated: {total_updated}."
