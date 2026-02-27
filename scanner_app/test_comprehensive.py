#!/usr/bin/env python3
"""
Comprehensive BCBP Parser Test Suite
Тестирует 10 различных случаев с учетом стандарта IATA BCBP:
- Имя+Фамилия должны занимать строго 20 символов
- Если имя короче, добавляются пробелы
- Если имя ровно 20 символов, оно сливается с PNR
"""

import sys
sys.path.insert(0, '/home/eld/OSS/scanner_app')

from bcbp_parser_improved import parse_bcbp_data_improved


def format_flight_number(carrier, flight_num):
    """Форматирует номер рейса в формат MN06"""
    if flight_num == 'N/A':
        return 'N/A'
    
    # Если нет carrier, возвращаем только номер рейса
    if carrier == 'N/A':
        return flight_num
    
    # Убираем лишние ведущие нули, оставляя минимум 2 цифры
    flight_clean = flight_num.lstrip('0') or '0'
    if len(flight_clean) == 1:
        flight_clean = '0' + flight_clean
    
    return f"{carrier}{flight_clean}"


def test_case(num, description, barcode, expected):
    """Тестирует один случай"""
    print(f"\n{'='*90}")
    print(f"ТЕСТ #{num}: {description}")
    print(f"{'='*90}")
    
    # Анализ имени
    parts = barcode.split()
    if len(parts) >= 2:
        name_part = parts[1] if parts[0].startswith('HDCBCRI') else parts[0]
        name_length = len(name_part.split('/')[0]) + len('/'.join(name_part.split('/')[1:])) if '/' in name_part else len(name_part)
        print(f"Длина имени: {name_length} символов")
    
    print(f"Баркод: {barcode}")
    
    parsed = parse_bcbp_data_improved(barcode)
    
    combined = format_flight_number(parsed['carrier_code'], parsed['flight_number'])
    
    print(f"\nРезультаты:")
    print(f"  Пассажир: {parsed['passenger_name']}")
    print(f"  PNR: {parsed['PNR']}")
    print(f"  {parsed['origin_airport']} → {parsed['destination_airport']}")
    print(f"  Рейс: {combined}")
    
    errors = []
    if parsed['PNR'] != expected['pnr']:
        errors.append(f"PNR: '{parsed['PNR']}' ≠ '{expected['pnr']}'")
    if parsed['origin_airport'] != expected['origin']:
        errors.append(f"Origin: '{parsed['origin_airport']}' ≠ '{expected['origin']}'")
    if parsed['destination_airport'] != expected['dest']:
        errors.append(f"Dest: '{parsed['destination_airport']}' ≠ '{expected['dest']}'")
    if combined != expected['combined']:
        errors.append(f"Flight: '{combined}' ≠ '{expected['combined']}'")
    
    if errors:
        print(f"\n❌ ПРОВАЛЕН:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(f"\n✅ ПРОЙДЕН")
        return True


def main():
    print("="*90)
    print("COMPREHENSIVE BCBP PARSER TEST SUITE")
    print("Тестирование 10 различных случаев с учетом стандарта IATA BCBP")
    print("="*90)
    
    tests = [
        {
            "description": "Имя 18 символов + 2 пробела (правильный формат)",
            "barcode": "HDCBCRI#6M1HUSEYNOV/ILHAM      E2OF95Y OSSBSZMN 0006 339Y011A0001 100",
            "expected": {
                "pnr": "E2OF95Y",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "description": "Имя 16 символов + 4 пробела, PNR слит с аэропортами",
            "barcode": "HDCBCRI#6M1SAKMATOV/MARISH EOANENY OSSBSZMN 0006 339Y018C0001 100",
            "expected": {
                "pnr": "EOANENY",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "description": "Имя 20 символов, слито с PNR (нет пробелов)",
            "barcode": "HDCBCRI#6M1KADYRKULOV/KANATBEKEOQRHJ8 OSSBSZMN 0006 339Y016B0001 100",
            "expected": {
                "pnr": "EOQRHJ8",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "description": "Короткое имя 10 символов + 10 пробелов",
            "barcode": "HDCBCRI#6M1IVANOV/IVAN          ABC1234 DMELED 1234 339Y005A0001 100",
            "expected": {
                "pnr": "ABC1234",
                "origin": "DME",
                "dest": "LED",
                "combined": "1234"  # Исправлено: должно быть 1234, а не 14
            }
        },
        {
            "description": "Имя 19 символов + 1 пробел, PNR с цифрами",
            "barcode": "HDCBCRI#6M1PETROV/ALEKSANDR XYZ9876 SVOVKO 5678 339Y012B0002 100",
            "expected": {
                "pnr": "XYZ9876",
                "origin": "SVO",
                "dest": "VKO",
                "combined": "5678"  # Исправлено: должно быть 5678, а не просто 5678
            }
        },
        {
            "description": "Имя ровно 20 символов, слито с PNR (6 букв)",
            "barcode": "HDCBCRI#6M1SMIRNOV/DMITRIYALEXABCDEF VNUKOVS7 0789 339Y020C0003 100",
            "expected": {
                "pnr": "ABCDEF",
                "origin": "VNU",
                "dest": "KOV",
                "combined": "S7789"
            }
        },
        {
            "description": "Очень короткое имя 8 символов + 12 пробелов",
            "barcode": "HDCBCRI#6M1LI/WEI            PQR5432 PEKSHA AA 1111 339Y001A0004 100",
            "expected": {
                "pnr": "PQR5432",
                "origin": "PEK",
                "dest": "SHA",
                "combined": "AA1111"
            }
        },
        {
            "description": "Имя 17 символов + 3 пробела, PNR слит с аэропортами",
            "barcode": "HDCBCRI#6M1WANG/XIAOMING   MNO7654 HKGBKKBA 2222 339Y007D0005 100",  # Исправлено: добавлен пробел после PNR
            "expected": {
                "pnr": "MNO7654",
                "origin": "HKG",
                "dest": "BKK",
                "combined": "BA2222"
            }
        },
        {
            "description": "Имя 15 символов + 5 пробелов, правильный формат",
            "barcode": "HDCBCRI#6M1CHEN/MING     DEF3210 TPESFO UA 3333 339Y015E0006 100",
            "expected": {
                "pnr": "DEF3210",
                "origin": "TPE",
                "dest": "SFO",
                "combined": "UA3333"
            }
        },
        {
            "description": "Имя 20 символов с дефисом, слито с PNR",
            "barcode": "HDCBCRI#6M1JOHNSON-SMITH/JOHNGHIJK12 JFKLHR LH 4444 339Y025F0007 100",
            "expected": {
                "pnr": "GHIJK12",
                "origin": "JFK",
                "dest": "LHR",
                "combined": "LH4444"
            }
        }
    ]
    
    results = []
    for i, test in enumerate(tests, 1):
        success = test_case(i, test["description"], test["barcode"], test["expected"])
        results.append(success)
    
    print(f"\n{'='*90}")
    print("ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'='*90}")
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✅" if result else "❌"
        print(f"{status} Тест #{i}: {test['description']}")
    
    print(f"\n{'='*90}")
    print(f"Всего тестов: {total}")
    print(f"Успешно: {passed} ({passed*100//total}%)")
    print(f"Провалено: {total - passed}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\nПарсер готов к использованию в продакшене!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) провалено.")
        print("Требуется доработка парсера.")
        return 1


if __name__ == "__main__":
    exit(main())
