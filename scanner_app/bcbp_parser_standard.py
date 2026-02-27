#!/usr/bin/env python3
"""
Standards-Based BCBP Parser with Fallback Strategies
Based on IATA Resolution 792 with handling for scanner variations
"""

import re
import datetime


def parse_bcbp_standard(barcode_string):
    """
    Парсит BCBP данные используя стандарт IATA Resolution 792
    с fallback-стратегиями для обработки вариаций от сканера
    """
    data = {
        'raw_barcode': barcode_string,
        'scanner_prefix': 'N/A',
        'pax_type': 'N/A',
        'passenger_name': 'N/A',
        'PNR': 'N/A',
        'origin_airport': 'N/A',
        'destination_airport': 'N/A',
        'carrier_code': 'N/A',
        'flight_number': 'N/A',
        'flight_date_info': 'N/A',
        'seat_number': 'N/A',
        'sequence_number': 'N/A',
        'additional_info_tail': 'N/A',
        'compartment_code': 'N/A',
    }

    # Очистка и извлечение префикса сканера
    cleaned_string = barcode_string.replace('\x02', '').replace('\x03', '').strip()
    data['raw_barcode'] = cleaned_string

    # Фильтрация HDCERR1
    if cleaned_string.startswith("HDCERR1") or not cleaned_string.strip():
        data['scanner_prefix'] = 'UNKNOWN_FORMAT'
        return data

    # Извлечение префикса сканера (HDCBCRI#6) но сохранение M1
    # Формат: HDCBCRI#6M1... -> извлекаем HDCBCRI#6, оставляем M1...
    scanner_prefix_match = re.match(r"^(HDCBCRI#\d)(M\d|INF)(.*)$", cleaned_string)
    
    if scanner_prefix_match:
        data['scanner_prefix'] = scanner_prefix_match.group(1)
        data['pax_type'] = scanner_prefix_match.group(2)
        # Сохраняем M1 в начале для стандартного парсинга
        bcbp_data = scanner_prefix_match.group(2) + scanner_prefix_match.group(3)
    else:
        bcbp_data = cleaned_string
        print(f"Warning: No scanner prefix found, using raw data")

    # СТРАТЕГИЯ 1: Парсинг по стандарту IATA (фиксированные позиции)
    try:
        if len(bcbp_data) >= 54:  # Минимальная длина для стандартного BCBP
            format_code = bcbp_data[0:1]
            num_legs = bcbp_data[1:2]
            
            if format_code == 'M' and num_legs.isdigit():
                # Стандартный формат IATA
                name_field = bcbp_data[2:22]
                pnr_field = bcbp_data[22:29]
                origin = bcbp_data[29:32]
                dest = bcbp_data[32:35]
                carrier = bcbp_data[35:37]
                flight = bcbp_data[37:42]
                date = bcbp_data[42:45]
                cabin = bcbp_data[45:46]
                seat = bcbp_data[46:50]
                sequence = bcbp_data[50:54]
                
                # Обработка имени
                name_clean = name_field.strip()
                if '/' in name_clean:
                    name_parts = name_clean.split('/')
                    data['passenger_name'] = f"{name_parts[0].strip()} / {' '.join(name_parts[1:]).strip()}"
                else:
                    data['passenger_name'] = name_clean
                
                data['PNR'] = pnr_field.strip()
                data['origin_airport'] = origin.strip()
                data['destination_airport'] = dest.strip()
                data['carrier_code'] = carrier.strip()
                data['flight_number'] = flight.strip()
                data['flight_date_info'] = date.strip()
                data['seat_number'] = seat.strip()
                data['sequence_number'] = sequence.strip()
                
                print(f"DEBUG: Parsed using IATA standard (fixed positions)")
                print(f"  Name field (pos 2-22): '{name_field}'")
                print(f"  PNR field (pos 22-29): '{pnr_field}'")
                print(f"  Airports (pos 29-35): {origin}{dest}")
                
                # Проверка валидности
                if data['PNR'] and data['origin_airport'] and data['destination_airport']:
                    return data
                else:
                    print(f"WARNING: Standard parsing produced invalid data, trying fallback")
    except Exception as e:
        print(f"WARNING: Standard IATA parsing failed: {e}")

    # СТРАТЕГИЯ 2: Fallback для неправильно отформатированных данных
    # Ищем 6-буквенную последовательность аэропортов с carrier code после
    print(f"DEBUG: Using fallback strategy for: '{bcbp_data}'")
    
    six_letters_pattern = re.compile(r"^(.+?)\s+([A-Z]{6})([A-Z0-9]{2,3}\s+\d+.*)$")
    match = six_letters_pattern.match(bcbp_data)
    
    if match:
        name_pnr_block = match.group(1).strip()
        airports = match.group(2)
        flight_details = match.group(3).strip()
        
        data['origin_airport'] = airports[0:3]
        data['destination_airport'] = airports[3:6]
        
        # Извлечение PNR из name_pnr_block
        # Пробуем с пробелом
        pnr_match = re.match(r"^(.+?)\s+([A-Z0-9]{5,7})$", name_pnr_block)
        if pnr_match:
            data['passenger_name'] = pnr_match.group(1).strip()
            data['PNR'] = pnr_match.group(2)
        else:
            # PNR слит с именем - берем последние 5-7 символов
            pnr_concat_match = re.match(r"^(.+)([A-Z0-9]{5,7})$", name_pnr_block)
            if pnr_concat_match and (re.search(r'\d', pnr_concat_match.group(2)) or len(pnr_concat_match.group(2)) >= 6):
                data['passenger_name'] = pnr_concat_match.group(1).strip()
                data['PNR'] = pnr_concat_match.group(2)
        
        # Обработка имени
        if '/' in data['passenger_name']:
            parts = data['passenger_name'].split('/')
            data['passenger_name'] = f"{parts[0].strip()} / {' '.join(parts[1:]).strip()}"
        
        # Извлечение carrier и flight
        flight_match = re.match(r"^([A-Z0-9]{2,3})\s+(\d+)\s*(.*)$", flight_details)
        if flight_match:
            potential_carrier = flight_match.group(1)
            potential_flight = flight_match.group(2)
            
            if re.search(r'[A-Z]', potential_carrier):
                data['carrier_code'] = potential_carrier
                data['flight_number'] = potential_flight
            else:
                data['flight_number'] = potential_carrier + potential_flight
        
        print(f"DEBUG: Fallback parsing successful")
        return data
    
    # СТРАТЕГИЯ 3: Правильный формат с пробелами
    standard_match = re.match(r"([A-Z0-9]{5,7})\s+([A-Z]{3})([A-Z]{3})([A-Z0-9]*.*)$", bcbp_data)
    if standard_match:
        data['PNR'] = standard_match.group(1)
        data['origin_airport'] = standard_match.group(2)
        data['destination_airport'] = standard_match.group(3)
        remaining = standard_match.group(4).strip()
        
        # Извлечение carrier/flight
        flight_match = re.match(r"^([A-Z0-9]{2,3})\s+(\d+)", remaining)
        if flight_match:
            data['carrier_code'] = flight_match.group(1)
            data['flight_number'] = flight_match.group(2)
        
        print(f"DEBUG: Standard format with spaces")
        return data

    print(f"ERROR: All parsing strategies failed")
    data['passenger_name'] = "ERROR_PARSING"
    data['PNR'] = "ERROR_PARSING"
    return data


def format_flight_number(carrier, flight_num):
    """Форматирует номер рейса в формат MN06"""
    if carrier == 'N/A' or flight_num == 'N/A':
        return 'N/A'
    
    # Убираем лишние ведущие нули, оставляя минимум 2 цифры
    flight_clean = flight_num.lstrip('0') or '0'
    if len(flight_clean) == 1:
        flight_clean = '0' + flight_clean
    
    return f"{carrier}{flight_clean}"


# Тестирование
if __name__ == "__main__":
    test_cases = [
        "HDCBCRI#6M1HUSEYNOV/ILHAM      E2OF95Y OSSBSZMN 0006 339Y011A0001 100",
        "HDCBCRI#6M1SAKMATOV/MARISH EOANENY OSSBSZMN 0006 339Y018C0001 100",
        "HDCBCRI#6M1KADYRKULOV/KANATBEKEOQRHJ8 OSSBSZMN 0006 339Y016B0001 100",
    ]
    
    for barcode in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {barcode}")
        print(f"{'='*80}")
        result = parse_bcbp_standard(barcode)
        print(f"Result:")
        print(f"  Name: {result['passenger_name']}")
        print(f"  PNR: {result['PNR']}")
        print(f"  Route: {result['origin_airport']} -> {result['destination_airport']}")
        print(f"  Flight: {format_flight_number(result['carrier_code'], result['flight_number'])}")
