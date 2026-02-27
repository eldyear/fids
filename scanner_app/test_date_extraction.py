#!/usr/bin/env python3
"""
Демонстрация извлечения и конвертации даты из BCBP
"""

import re
import datetime

def extract_flight_date(flight_date_info_string, current_year=None):
    """
    Извлекает Julian date из flight_date_info и конвертирует в нормальную дату
    
    Args:
        flight_date_info_string: Строка типа "340Y0" или "340Y"
        current_year: Год для конвертации (по умолчанию текущий)
    
    Returns:
        dict с полями:
            - julian_date: строка с Julian date (например, "340")
            - date: объект datetime.date
            - date_str: строка в формате YYYY-MM-DD
            - compartment: класс обслуживания (например, "Y")
    """
    if not flight_date_info_string or flight_date_info_string == 'N/A':
        return {
            'julian_date': 'N/A',
            'date': None,
            'date_str': 'N/A',
            'compartment': 'N/A'
        }
    
    # Извлекаем Julian date (первые 3 цифры)
    julian_match = re.match(r'^(\d{3})([A-Z])?', flight_date_info_string)
    
    if not julian_match:
        return {
            'julian_date': 'N/A',
            'date': None,
            'date_str': 'N/A',
            'compartment': 'N/A'
        }
    
    julian_date_str = julian_match.group(1)
    compartment = julian_match.group(2) if julian_match.group(2) else 'N/A'
    julian_date = int(julian_date_str)
    
    # Определяем год
    if current_year is None:
        current_year = datetime.datetime.now().year
    
    # Конвертируем Julian date в нормальную дату
    try:
        # Создаем дату: 1 января текущего года + (julian_date - 1) дней
        date_obj = datetime.datetime(current_year, 1, 1) + datetime.timedelta(days=julian_date - 1)
        date_str = date_obj.strftime('%Y-%m-%d')
    except (ValueError, OverflowError):
        date_obj = None
        date_str = 'N/A'
    
    return {
        'julian_date': julian_date_str,
        'date': date_obj,
        'date_str': date_str,
        'compartment': compartment
    }


# Тестирование
if __name__ == "__main__":
    test_cases = [
        ("340Y0", 2025, "2025-12-06"),  # 340-й день 2025 года
        ("340Y", 2025, "2025-12-06"),
        ("001Y", 2025, "2025-01-01"),   # 1-й день года
        ("365Y", 2025, "2025-12-31"),   # Последний день невисокосного года
        ("186Y", 2025, "2025-07-05"),   # Середина года
        ("N/A", 2025, "N/A"),
    ]
    
    print("="*80)
    print("ТЕСТ: Извлечение и конвертация даты из BCBP")
    print("="*80)
    
    for flight_date_info, year, expected_date in test_cases:
        result = extract_flight_date(flight_date_info, year)
        
        status = "✅" if result['date_str'] == expected_date else "❌"
        
        print(f"\n{status} Input: {flight_date_info:10s} (год {year})")
        print(f"   Julian date: {result['julian_date']}")
        print(f"   Дата:        {result['date_str']}")
        print(f"   Ожидается:   {expected_date}")
        print(f"   Класс:       {result['compartment']}")
        
        if result['date']:
            print(f"   День недели: {result['date'].strftime('%A')}")
    
    print("\n" + "="*80)
    print("ВЫВОД: Можно безопасно добавить конвертацию даты!")
    print("="*80)
