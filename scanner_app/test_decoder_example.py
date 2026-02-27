#!/usr/bin/env python3
"""
Тест парсера с примером из BCBP декодера
"""

import sys
sys.path.insert(0, '/home/eld/OSS/scanner_app')

from bcbp_parser_improved import parse_bcbp_data_improved as parse_bcbp_data

# Тестовый баркод из декодера
# Оригинал: M1MUSURMANKULOV/TURDALE12QU23 OSSBSZK9 0112 340Y002B0099 100
# С префиксом сканера:
test_barcode = "HDCBCRI#6M1MUSURMANKULOV/TURDALE12QU23 OSSBSZK9 0112 340Y002B0099 100"

print("="*80)
print("ТЕСТ: Пример из BCBP декодера")
print("="*80)
print(f"Баркод: {test_barcode}")
print()

# Парсим
result = parse_bcbp_data(test_barcode)

print("РЕЗУЛЬТАТЫ ПАРСИНГА:")
print("-"*80)
print(f"Format Code:        M1 (ожидается: M)")
print(f"Number of Legs:     1 (ожидается: 1)")
print(f"Passenger Name:     {result['passenger_name']}")
print(f"  Ожидается:        MUSURMANKULOV / TURDAL")
print()
print(f"PNR:                {result['PNR']}")
print(f"  Ожидается:        E12QU23 (или 12QU23)")
print()
print(f"Origin:             {result['origin_airport']}")
print(f"  Ожидается:        OSS")
print()
print(f"Destination:        {result['destination_airport']}")
print(f"  Ожидается:        BSZ")
print()
print(f"Airline Code:       {result['carrier_code']}")
print(f"  Ожидается:        K9")
print()
print(f"Flight Number:      {result['flight_number']}")
print(f"  Ожидается:        0112")
print()
print(f"Flight Date:        {result['flight_date_info']}")
print(f"  Ожидается:        340Y (Julian date для 2025-12-06)")
print()
print(f"Compartment:        {result['compartment_code']}")
print(f"  Ожидается:        (часть flight_date_info)")
print()
print(f"Seat Number:        {result['seat_number']}")
print(f"  Ожидается:        002B")
print()
print(f"Check-in Sequence:  {result['sequence_number']}")
print(f"  Ожидается:        0099")
print()

# Проверка
errors = []
if result['passenger_name'] != "MUSURMANKULOV / TURDAL":
    errors.append(f"Passenger Name: '{result['passenger_name']}' ≠ 'MUSURMANKULOV / TURDAL'")

# PNR может быть E12QU23 или 12QU23 (с или без E - electronic ticket indicator)
if result['PNR'] not in ['E12QU23', '12QU23']:
    errors.append(f"PNR: '{result['PNR']}' не соответствует ожидаемому (E12QU23 или 12QU23)")

if result['origin_airport'] != 'OSS':
    errors.append(f"Origin: '{result['origin_airport']}' ≠ 'OSS'")

if result['destination_airport'] != 'BSZ':
    errors.append(f"Destination: '{result['destination_airport']}' ≠ 'BSZ'")

if result['carrier_code'] != 'K9':
    errors.append(f"Carrier: '{result['carrier_code']}' ≠ 'K9'")

if result['flight_number'] != '0112':
    errors.append(f"Flight Number: '{result['flight_number']}' ≠ '0112'")

# Flight date info включает дату и класс: 340Y
if not result['flight_date_info'].startswith('340'):
    errors.append(f"Flight Date: '{result['flight_date_info']}' не начинается с '340'")

if result['seat_number'] != '002B':
    errors.append(f"Seat: '{result['seat_number']}' ≠ '002B'")

if result['sequence_number'] != '0099':
    errors.append(f"Sequence: '{result['sequence_number']}' ≠ '0099'")

print("="*80)
if errors:
    print("❌ ЕСТЬ РАСХОЖДЕНИЯ:")
    for error in errors:
        print(f"  - {error}")
    print()
    print("ПРИМЕЧАНИЕ:")
    print("В стандарте IATA BCBP:")
    print("- 'E' в начале PNR означает Electronic Ticket indicator")
    print("- Compartment Code (Y) включен в flight_date_info (340Y)")
else:
    print("✅ ВСЕ ПОЛЯ СООТВЕТСТВУЮТ ОЖИДАЕМЫМ!")
print("="*80)
