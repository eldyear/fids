#!/usr/bin/env python3
"""
Standalone тест для парсера BCBP (Bar Coded Boarding Pass)
Проверяет как правильные, так и неправильные форматы баркодов
"""

import re


def parse_bcbp_data(barcode_string):
    """Парсит BCBP данные (копия функции из scanner_websocket_bridge.py)"""
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

    cleaned_string = barcode_string.replace('\x02', '').replace('\x03', '').strip()
    data['raw_barcode'] = cleaned_string

    # 1. Отфильтровываем HDCERR1
    if cleaned_string.startswith("HDCERR1") or not cleaned_string.strip():
        data['scanner_prefix'] = 'UNKNOWN_FORMAT'
        return data

    # 2. Извлечение внешнего префикса сканера и типа пассажира
    initial_block_regex = re.compile(
        r"^(HDCBCRI#\d)(M\d|INF)\s*(.*)$"
    )
    initial_match = initial_block_regex.match(cleaned_string)

    content_after_initial_prefix = cleaned_string

    if initial_match:
        data['scanner_prefix'] = initial_match.group(1)
        data['pax_type'] = initial_match.group(2)
        content_after_initial_prefix = initial_match.group(3).strip()
    else:
        print(f"Warning: Unexpected start for BCBP string: {cleaned_string}")

    # 3. Извлечение имени пассажира и PNR
    pnr_marker_regex = re.compile(r"([A-Z0-9]{5,7})\s+([A-Z]{3})([A-Z]{3})([A-Z0-9]*.*)$")
    pnr_marker_match = pnr_marker_regex.search(content_after_initial_prefix)

    raw_name_candidate = content_after_initial_prefix
    remaining_string_for_flight_details = ""

    if pnr_marker_match:
        data['PNR'] = pnr_marker_match.group(1)
        data['origin_airport'] = pnr_marker_match.group(2)
        data['destination_airport'] = pnr_marker_match.group(3)
        raw_name_candidate = content_after_initial_prefix[:pnr_marker_match.start(1)].strip()
        remaining_string_for_flight_details = pnr_marker_match.group(4).strip()
    else:
        print(f"Warning: PNR with airport marker not found (expected space) in: '{content_after_initial_prefix}'")

        name_pnr_and_flight_start_regex = re.compile(r"(.+?)([A-Z]{3}[A-Z]{3}[A-Z0-9]*\s*\d+.*)$")
        name_pnr_and_flight_start_match = name_pnr_and_flight_start_regex.match(content_after_initial_prefix)

        name_pnr_block_temp = content_after_initial_prefix
        if name_pnr_and_flight_start_match:
            name_pnr_block_temp = name_pnr_and_flight_start_match.group(1).strip()
            remaining_string_for_flight_details = name_pnr_and_flight_start_match.group(2).strip()
        else:
            print(f"ERROR: Could not find airport marker for flight details in '{content_after_initial_prefix}'")
            data['passenger_name'] = "ERROR_PARSING"
            data['PNR'] = "ERROR_PARSING"
            return data

        pnr_extract_regex = re.compile(r"(.+?)([A-Z0-9]{5,7})$")
        pnr_extract_match = pnr_extract_regex.match(name_pnr_block_temp)

        if pnr_extract_match:
            raw_name_candidate = pnr_extract_match.group(1).strip()
            data['PNR'] = pnr_extract_match.group(2).strip()
        else:
            raw_name_candidate = name_pnr_block_temp.strip()
            data['PNR'] = 'N/A'

    # Обработка имени
    processed_name = raw_name_candidate.replace('<', ' ').strip()
    if '/' in processed_name:
        name_parts = processed_name.split('/')
        if len(name_parts) > 1:
            data['passenger_name'] = f"{name_parts[0].strip()} / {' '.join(name_parts[1:]).strip()}"
        else:
            data['passenger_name'] = name_parts[0].strip()
    else:
        data['passenger_name'] = processed_name.strip()

    # 4. Если аэропорты еще не были извлечены (случай со слитым PNR), извлекаем их здесь
    if data['origin_airport'] == 'N/A' and data['destination_airport'] == 'N/A' and remaining_string_for_flight_details:
        airport_carrier_match = re.match(r"^([A-Z]{3})([A-Z]{3})([A-Z0-9]{1,3})?", remaining_string_for_flight_details)
        if airport_carrier_match:
            data['origin_airport'] = airport_carrier_match.group(1)
            data['destination_airport'] = airport_carrier_match.group(2)
            if airport_carrier_match.group(3):
                data['carrier_code'] = airport_carrier_match.group(3)
            remaining_string_for_flight_details = remaining_string_for_flight_details[airport_carrier_match.end():].strip()
        elif len(remaining_string_for_flight_details) >= 3:
             data['origin_airport'] = remaining_string_for_flight_details[0:3]
             remaining_string_for_flight_details = remaining_string_for_flight_details[3:].strip()

    # 5. Извлечение Carrier Code и Flight Number
    flight_details_regex = re.compile(
        r"^([A-Z0-9]{2,3})\s*([A-Z0-9]{1,5})\s*(.*)$"
    )
    
    flight_match = flight_details_regex.match(remaining_string_for_flight_details)

    if flight_match:
        data['carrier_code'] = flight_match.group(1).strip()
        data['flight_number'] = flight_match.group(2).strip()
        remaining_string_for_flight_details = flight_match.group(3).strip()
        print(f"DEBUG: Извлечено Flight (regex): Carrier={data['carrier_code']}, Flight={data['flight_number']}")
    else:
        parts_of_flight_details = re.split(r'\s+', remaining_string_for_flight_details)
        parts_of_flight_details = [p for p in parts_of_flight_details if p]
        current_segment_index = 0

        if len(parts_of_flight_details) > current_segment_index:
            candidate_carrier_or_flight = parts_of_flight_details[current_segment_index]
            
            carrier_like_regex = re.compile(r"^[A-Z0-9]{2,3}$")
            if carrier_like_regex.match(candidate_carrier_or_flight):
                data['carrier_code'] = candidate_carrier_or_flight
                current_segment_index += 1
                
                if len(parts_of_flight_details) > current_segment_index:
                    candidate_flight_number = parts_of_flight_details[current_segment_index]
                    if re.match(r"^[A-Z0-9]{1,5}$", candidate_flight_number):
                        data['flight_number'] = candidate_flight_number
                        current_segment_index += 1
                print(f"DEBUG: Извлечено Flight (сегменты): Carrier={data['carrier_code']}, Flight={data['flight_number']}")
            elif candidate_carrier_or_flight.isdigit():
                data['flight_number'] = candidate_carrier_or_flight
                current_segment_index += 1
                print(f"DEBUG: Извлечено Flight (только номер): Flight={data['flight_number']}")
            else:
                print(f"Warning: Unparsed initial flight/carrier segment: '{candidate_carrier_or_flight}'")
            
            remaining_string_for_flight_details = " ".join(parts_of_flight_details[current_segment_index:]).strip()

    # 6. Парсинг сложного блока: Дата/Класс, Место, SEQ
    if remaining_string_for_flight_details:
        complex_data_segment = remaining_string_for_flight_details.strip()
        
        temp_date = 'N/A'
        temp_seat = 'N/A'
        temp_sequence = 'N/A'
        temp_compartment = 'N/A'

        flight_date_match = re.match(r"^(\d{3}[A-Z]{1,2}\d{0,1})", complex_data_segment)
        if flight_date_match:
            temp_date = flight_date_match.group(1)
            complex_data_segment = complex_data_segment[len(temp_date):].strip()

        seat_number_match = re.match(r"^(\d{2,3}[A-Z]{1,2})", complex_data_segment)
        if seat_number_match:
            temp_seat = seat_number_match.group(1)
            complex_data_segment = complex_data_segment[len(temp_seat):].strip()

        sequence_number_match = re.search(r"(\d{3,4})$", complex_data_segment)
        if sequence_number_match:
            temp_sequence = sequence_number_match.group(1)
            complex_data_segment = complex_data_segment[:-len(temp_sequence)].strip()

        if len(complex_data_segment) > 0:
            temp_compartment = complex_data_segment

        if temp_date != 'N/A':
            data['flight_date_info'] = temp_date
        if temp_seat != 'N/A':
            data['seat_number'] = temp_seat
        if temp_sequence != 'N/A':
            data['sequence_number'] = temp_sequence
        if temp_compartment != 'N/A':
            data['compartment_code'] = temp_compartment

        if data['seat_number'] == '00NO':
            data['seat_number'] = '00'
            data['compartment_code'] = 'NO'
        
        remaining_string_for_flight_details = ''

    # 7. Дополнительная информация в конце строки
    if remaining_string_for_flight_details:
        data['additional_info_tail'] = remaining_string_for_flight_details.strip()

    # Финальная проверка и корректировка carrier_code и flight_number
    if data['flight_number'] == 'N/A' and data['carrier_code'] != 'N/A' and re.match(r"^\d+$", data['carrier_code']):
        data['flight_number'] = data['carrier_code']
        data['carrier_code'] = 'N/A'

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


def print_test_result(test_num, barcode, description, expected):
    """Выполняет тест и выводит результат"""
    print(f"\n{'='*80}")
    print(f"ТЕСТ #{test_num}: {description}")
    print(f"{'='*80}")
    print(f"Баркод: {barcode}")
    print(f"{'-'*80}")
    
    parsed = parse_bcbp_data(barcode)
    
    # Выводим результаты парсинга
    print(f"Пассажир: {parsed['passenger_name']}")
    print(f"PNR: {parsed['PNR']}")
    print(f"Откуда: {parsed['origin_airport']}")
    print(f"Куда: {parsed['destination_airport']}")
    print(f"Перевозчик: {parsed['carrier_code']}")
    print(f"Номер рейса: {parsed['flight_number']}")
    
    combined = format_flight_number(parsed['carrier_code'], parsed['flight_number'])
    print(f">>> Комбинированный рейс: {combined}")
    
    # Проверяем ожидаемые значения
    errors = []
    if parsed['PNR'] != expected['pnr']:
        errors.append(f"PNR: получено '{parsed['PNR']}', ожидалось '{expected['pnr']}'")
    if parsed['origin_airport'] != expected['origin']:
        errors.append(f"Origin: получено '{parsed['origin_airport']}', ожидалось '{expected['origin']}'")
    if parsed['destination_airport'] != expected['dest']:
        errors.append(f"Dest: получено '{parsed['destination_airport']}', ожидалось '{expected['dest']}'")
    if combined != expected['combined']:
        errors.append(f"Combined flight: получено '{combined}', ожидалось '{expected['combined']}'")
    
    if errors:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(f"\n✅ ТЕСТ ПРОЙДЕН")
        return True


def main():
    print("="*80)
    print("ТЕСТИРОВАНИЕ ПАРСЕРА BCBP")
    print("="*80)
    
    tests = [
        {
            "barcode": "HDCBCRI#6M1HUSEYNOV/ILHAM      E2OF95Y OSSBSZMN 0006 339Y011A0001 100",
            "description": "✅ ПРАВИЛЬНЫЙ формат (с пробелами)",
            "expected": {
                "pnr": "E2OF95Y",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "barcode": "HDCBCRI#6M1SAKMATOV/MARISH EOANENY OSSBSZMN 0006 339Y018C0001 100",
            "description": "❌ НЕПРАВИЛЬНЫЙ формат (PNR слит с аэропортами)",
            "expected": {
                "pnr": "EOANENY",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "barcode": "HDCBCRI#6M1KADYRKULOV/KANATBEK EOQRHJ8 OSSBSZMN 0006 339Y016B0001 100",
            "description": "❌ НЕПРАВИЛЬНЫЙ формат (непонятная структура)",
            "expected": {
                "pnr": "EOQRHJ8",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        }
    ]
    
    results = []
    for i, test in enumerate(tests, 1):
        success = print_test_result(i, test["barcode"], test["description"], test["expected"])
        results.append(success)
    
    # Итоговый отчет
    print(f"\n{'='*80}")
    print("ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'='*80}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Всего тестов: {total}")
    print(f"Успешно: {passed}")
    print(f"Провалено: {total - passed}")
    
    if passed == total:
        print("\n🎉 Все тесты пройдены!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) провалено. Требуется улучшение парсера.")
        return 1


if __name__ == "__main__":
    exit(main())
