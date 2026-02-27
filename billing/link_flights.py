# flights/link_flights.py
from .models import Flight
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

def link_arrival_departure_flights(target_date):
    """
    Автоматически связывает прилетающие и вылетающие рейсы на основе
    даты, авиакомпании, бортового номера и зеркальных аэропортов.
    """
    logger.info(f"Начинаю автоматическое связывание рейсов для даты: {target_date}")
    
    # Получаем все рейсы за указанную дату, которые еще не связаны
    flights_for_date = Flight.objects.filter(date=target_date, linked_flight__isnull=True).order_by('time')

    unlinked_flights_by_board_num = {}
    for flight in flights_for_date:
        if flight.board_num: # Нужен бортовой номер для связывания
            key = (flight.airline, flight.board_num)
            if key not in unlinked_flights_by_board_num:
                unlinked_flights_by_board_num[key] = []
            unlinked_flights_by_board_num[key].append(flight)

    # flights/link_flights.py
from .models import Flight
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

def link_arrival_departure_flights(target_date):
    """
    Автоматически связывает рейсы на основе
    даты, авиакомпании, бортового номера и зеркальных аэропортов.
    """
    logger.info(f"Начинаю автоматическое связывание рейсов для даты: {target_date}")
    
    # Получаем все рейсы за указанную дату, которые еще не связаны
    flights_for_date = Flight.objects.filter(date=target_date, linked_flight__isnull=True).order_by('time')

    linked_count = 0
    with transaction.atomic():
        for current_flight in flights_for_date:
            # Проверяем, что у рейса есть все нужные поля для связывания
            if not current_flight.board_num or not current_flight.airline or not current_flight.dep_airport or not current_flight.arr_airport:
                continue

            # Ищем обратный рейс
            related_flight = Flight.objects.filter(
                date=target_date,
                board_num=current_flight.board_num,
                airline=current_flight.airline,
                # Аэропорты должны быть зеркальными
                dep_airport=current_flight.arr_airport,
                arr_airport=current_flight.dep_airport,
                linked_flight__isnull=True  # Ищем только несвязанные
            ).exclude(id=current_flight.id).first()
            
            if related_flight:
                # Связываем оба рейса друг с другом
                current_flight.linked_flight = related_flight
                related_flight.linked_flight = current_flight
                
                current_flight.save(update_fields=['linked_flight'])
                related_flight.save(update_fields=['linked_flight'])
                linked_count += 2
                logger.info(f"Связаны рейсы: {current_flight.flight_num} и {related_flight.flight_num} по борту {current_flight.board_num}.")

    logger.info(f"Завершено связывание рейсов для даты {target_date}. Связано пар: {linked_count // 2}")
    return linked_count // 2 # Возвращаем количество пар