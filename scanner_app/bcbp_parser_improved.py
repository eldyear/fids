#!/usr/bin/env python3
"""
Улучшенная версия парсера BCBP с поддержкой неправильных форматов
"""

import re


def parse_bcbp_data_improved(barcode_string):
    """
    Улучшенная версия парсера BCBP с множественными стратегиями для обработки
    неправильных форматов, где PNR слит с аэропортами
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

    # 3. УЛУЧШЕННОЕ извлечение имени пассажира, PNR и аэропортов
    # КЛЮЧЕВАЯ ИДЕЯ: Сначала ищем 6-буквенную последовательность аэропортов (OSSBSZ),
    # так как это более надежный индикатор, чем PNR
    # ВАЖНО: После аэропортов должен идти carrier code (2-3 буквы/цифры) или цифры
    
    raw_name_candidate = content_after_initial_prefix
    remaining_string_for_flight_details = ""
    
    # Стратегия 1: Ищем 6 заглавных букв подряд, после которых идет carrier/flight паттерн
    # Паттерн: [текст] [пробел] [6 букв] [2-3 символа или цифры] [пробел] [цифры]
    # Пример: "SAKMATOV/MARISH EOANENY OSSBSZMN 0006..." -> OSSBSZ это аэропорты (за ними MN 0006)
    # НЕ подходит: "EOANENY" потому что за ним идет "OSSBSZ" (еще 6 букв), а не carrier
    six_letters_with_carrier_pattern = re.compile(r"^(.+?)\s+([A-Z]{6})([A-Z0-9]{2,3}\s+\d+.*)$")
    six_letters_match = six_letters_with_carrier_pattern.match(content_after_initial_prefix)
    
    if six_letters_match:
        # Нашли 6-буквенную последовательность с carrier/flight после нее
        name_and_pnr_block = six_letters_match.group(1).strip()
        airports_6letter = six_letters_match.group(2)
        remaining_string_for_flight_details = six_letters_match.group(3).strip()
        
        # Разбиваем 6 букв на два аэропорта
        data['origin_airport'] = airports_6letter[0:3]
        data['destination_airport'] = airports_6letter[3:6]
        
        print(f"DEBUG: Найдены аэропорты (6-буквенная последовательность + carrier): {data['origin_airport']}->{data['destination_airport']}")
        
        # Теперь извлекаем PNR из name_and_pnr_block
        # PNR обычно 5-7 символов, последнее слово перед аэропортами
        # Паттерн: [имя] [пробел] [PNR]
        pnr_extract_regex = re.compile(r"^(.+?)\s+([A-Z0-9]{5,7})$")
        pnr_extract_match = pnr_extract_regex.match(name_and_pnr_block)
        
        if pnr_extract_match:
            raw_name_candidate = pnr_extract_match.group(1).strip()
            data['PNR'] = pnr_extract_match.group(2)
            print(f"DEBUG: Извлечен PNR (с пробелом): {data['PNR']}")
        else:
            # Если не нашли с пробелом, возможно PNR слит с именем
            # Пример: "KADYRKULOV/KANATBEKEOQRHJ8" -> PNR = "EOQRHJ8"
            # Ищем последние 5-7 символов, ПРИОРИТЕТ на 7 символов
            pnr_7_regex = re.compile(r"^(.+?)([A-Z0-9]{7})$")
            pnr_6_regex = re.compile(r"^(.+?)([A-Z0-9]{6})$")
            pnr_5_regex = re.compile(r"^(.+?)([A-Z0-9]{5})$")
            
            pnr_extracted = False
            # Пробуем сначала 7 символов, потом 6, потом 5
            for pnr_regex in [pnr_7_regex, pnr_6_regex, pnr_5_regex]:
                pnr_at_end_match = pnr_regex.match(name_and_pnr_block)
                if pnr_at_end_match:
                    potential_name = pnr_at_end_match.group(1)
                    potential_pnr = pnr_at_end_match.group(2)
                    
                    # Проверяем, что это действительно PNR
                    # PNR может быть только буквами (ABCDEF) или с цифрами (EOQRHJ8)
                    # Главное - это НЕ должно быть частью имени
                    # Проверяем что перед ним есть разделитель ИЛИ это достаточно длинный код
                    is_valid_pnr = False
                    
                    if potential_name.endswith('/') or potential_name.endswith(' '):
                        # Четкий разделитель - это точно PNR
                        is_valid_pnr = True
                    elif len(potential_pnr) >= 6:
                        # Для 6+ символов проверяем, что это не просто конец имени
                        # Если в potential_pnr есть цифры, это скорее всего PNR
                        # Если только буквы, проверяем что в имени есть "/" (значит имя полное)
                        if re.search(r'\d', potential_pnr):
                            is_valid_pnr = True
                        elif len(potential_pnr) == 6 and '/' in potential_name:
                            # 6 букв после полного имени (с /) - вероятно PNR
                            is_valid_pnr = True
                    
                    if is_valid_pnr:
                        raw_name_candidate = potential_name.strip()
                        data['PNR'] = potential_pnr
                        pnr_extracted = True
                        print(f"DEBUG: Извлечен PNR (слит с именем, {len(potential_pnr)} символов): {data['PNR']}")
                        break
            
            if not pnr_extracted:
                # Пробуем взять последнее слово
                words = name_and_pnr_block.split()
                if words and 5 <= len(words[-1]) <= 7:
                    data['PNR'] = words[-1]
                    raw_name_candidate = ' '.join(words[:-1])
                    print(f"DEBUG: Извлечен PNR (последнее слово): {data['PNR']}")
                else:
                    raw_name_candidate = name_and_pnr_block
                    data['PNR'] = 'N/A'
                    print(f"WARNING: Не удалось извлечь PNR из: '{name_and_pnr_block}'")
    else:
        # Стратегия 2: Попытка найти PNR с пробелом и отдельными аэропортами (правильный формат)
        # Паттерн: [имя] [PNR] [пробел] [3 буквы] [3 буквы] [остальное]
        pnr_marker_regex = re.compile(r"([A-Z0-9]{5,7})\s+([A-Z]{3})([A-Z]{3})([A-Z0-9]*.*)$")
        pnr_marker_match = pnr_marker_regex.search(content_after_initial_prefix)
        
        if pnr_marker_match:
            # Правильный формат: PNR [пробел] ORIGIN DEST
            data['PNR'] = pnr_marker_match.group(1)
            data['origin_airport'] = pnr_marker_match.group(2)
            data['destination_airport'] = pnr_marker_match.group(3)
            raw_name_candidate = content_after_initial_prefix[:pnr_marker_match.start(1)].strip()
            remaining_string_for_flight_details = pnr_marker_match.group(4).strip()
            print(f"DEBUG: Извлечено (правильный формат): PNR={data['PNR']}, {data['origin_airport']}->{data['destination_airport']}")
        else:
            # Стратегия 3: Ищем любые 6 букв подряд в строке (без пробела перед ними)
            six_letters_anywhere = re.compile(r"([A-Z]{6})")
            six_letters_matches = list(six_letters_anywhere.finditer(content_after_initial_prefix))
            
            if six_letters_matches:
                # Берем первое совпадение как аэропорты
                first_match = six_letters_matches[0]
                airports_6letter = first_match.group(1)
                
                data['origin_airport'] = airports_6letter[0:3]
                data['destination_airport'] = airports_6letter[3:6]
                
                # Все до аэропортов - это имя и PNR
                name_and_pnr_block = content_after_initial_prefix[:first_match.start()].strip()
                # Все после аэропортов - это детали рейса
                remaining_string_for_flight_details = content_after_initial_prefix[first_match.end():].strip()
                
                print(f"DEBUG: Найдены аэропорты (поиск в строке): {data['origin_airport']}->{data['destination_airport']}")
                
                # Извлекаем PNR из name_and_pnr_block
                words = name_and_pnr_block.split()
                if words and 5 <= len(words[-1]) <= 7:
                    data['PNR'] = words[-1]
                    raw_name_candidate = ' '.join(words[:-1])
                    print(f"DEBUG: Извлечен PNR (последнее слово): {data['PNR']}")
                else:
                    raw_name_candidate = name_and_pnr_block
                    data['PNR'] = 'N/A'
            else:
                # Не удалось найти аэропорты вообще
                print(f"ERROR: Could not find airport codes in '{content_after_initial_prefix}'")
                data['passenger_name'] = "ERROR_PARSING"
                data['PNR'] = "ERROR_PARSING"
                return data

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

    # 4. Если аэропорты еще не были извлечены, извлекаем их здесь
    if data['origin_airport'] == 'N/A' and data['destination_airport'] == 'N/A' and remaining_string_for_flight_details:
        airport_carrier_match = re.match(r"^([A-Z]{3})([A-Z]{3})([A-Z0-9]{1,3})?", remaining_string_for_flight_details)
        if airport_carrier_match:
            data['origin_airport'] = airport_carrier_match.group(1)
            data['destination_airport'] = airport_carrier_match.group(2)
            if airport_carrier_match.group(3):
                data['carrier_code'] = airport_carrier_match.group(3)
            remaining_string_for_flight_details = remaining_string_for_flight_details[airport_carrier_match.end():].strip()

    # 5. Извлечение Carrier Code и Flight Number (УЛУЧШЕННАЯ ЛОГИКА)
    # ВАЖНО: Carrier code должен содержать хотя бы одну букву
    # Если это только цифры, то это flight number без carrier code
    
    flight_details_regex = re.compile(
        r"^([A-Z0-9]{2,3})\s*([A-Z0-9]{1,5})\s*(.*)$"
    )
    
    flight_match = flight_details_regex.match(remaining_string_for_flight_details)

    if flight_match:
        potential_carrier = flight_match.group(1).strip()
        potential_flight = flight_match.group(2).strip()
        
        # Проверяем, что carrier содержит хотя бы одну букву
        if re.search(r'[A-Z]', potential_carrier):
            # Это действительно carrier code
            data['carrier_code'] = potential_carrier
            data['flight_number'] = potential_flight
            remaining_string_for_flight_details = flight_match.group(3).strip()
            print(f"DEBUG: Извлечено Flight (regex): Carrier={data['carrier_code']}, Flight={data['flight_number']}")
        else:
            # Это не carrier, а часть номера рейса (например "123 4" вместо "AA 1234")
            # НО проверяем: если potential_flight тоже только цифры и короткий, это может быть "1234" разбитое на "123" и "4"
            # В этом случае объединяем
            if potential_flight.isdigit() and len(potential_carrier) <= 4:
                data['flight_number'] = potential_carrier + potential_flight
                remaining_string_for_flight_details = flight_match.group(3).strip()
                print(f"DEBUG: Извлечено Flight (только номер, без carrier): Flight={data['flight_number']}")
            else:
                # Иначе это действительно carrier без букв (что странно, но возможно)
                data['carrier_code'] = potential_carrier
                data['flight_number'] = potential_flight
                remaining_string_for_flight_details = flight_match.group(3).strip()
                print(f"DEBUG: Извлечено Flight (numeric carrier): Carrier={data['carrier_code']}, Flight={data['flight_number']}")
    else:
        parts_of_flight_details = re.split(r'\s+', remaining_string_for_flight_details)
        parts_of_flight_details = [p for p in parts_of_flight_details if p]
        current_segment_index = 0

        if len(parts_of_flight_details) > current_segment_index:
            candidate_carrier_or_flight = parts_of_flight_details[current_segment_index]
            
            carrier_like_regex = re.compile(r"^[A-Z0-9]{2,3}$")
            if carrier_like_regex.match(candidate_carrier_or_flight) and re.search(r'[A-Z]', candidate_carrier_or_flight):
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

    # 7. Дополнительная информация
    if remaining_string_for_flight_details:
        data['additional_info_tail'] = remaining_string_for_flight_details.strip()

    # Финальная проверка
    if data['flight_number'] == 'N/A' and data['carrier_code'] != 'N/A' and re.match(r"^\d+$", data['carrier_code']):
        data['flight_number'] = data['carrier_code']
        data['carrier_code'] = 'N/A'

    return data


# Тестирование
if __name__ == "__main__":
    test_cases = [
        "HDCBCRI#6M1HUSEYNOV/ILHAM      E2OF95Y OSSBSZMN 0006 339Y011A0001 100",
        "HDCBCRI#6M1SAKMATOV/MARISH EOANENY OSSBSZMN 0006 339Y018C0001 100",
        "HDCBCRI#6M1KADYRKULOV/KANATBEK EOQRHJ8 OSSBSZMN 0006 339Y016B0001 100",
    ]
    
    for barcode in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {barcode}")
        print(f"{'='*80}")
        result = parse_bcbp_data_improved(barcode)
        print(f"PNR: {result['PNR']}")
        print(f"Origin: {result['origin_airport']}")
        print(f"Dest: {result['destination_airport']}")
        print(f"Carrier: {result['carrier_code']}")
        print(f"Flight: {result['flight_number']}")
