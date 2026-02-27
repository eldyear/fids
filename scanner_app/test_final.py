#!/usr/bin/env python3
"""
Финальный тест улучшенного парсера BCBP
"""

import sys
sys.path.insert(0, '/home/eld/OSS/scanner_app')

from bcbp_parser_improved import parse_bcbp_data_improved


def format_flight_number(carrier, flight_num):
    """Форматирует номер рейса в формат MN06"""
    if carrier == 'N/A' or flight_num == 'N/A':
        return 'N/A'
    
    # Убираем лишние ведущие нули, оставляя минимум 2 цифры
    flight_clean = flight_num.lstrip('0') or '0'
    if len(flight_clean) == 1:
        flight_clean = '0' + flight_clean
    
    return f"{carrier}{flight_clean}"


def test_case(num, barcode, expected):
    """Тестирует один случай"""
    print(f"\n{'='*80}")
    print(f"ТЕСТ #{num}")
    print(f"{'='*80}")
    print(f"Баркод: {barcode}")
    
    parsed = parse_bcbp_data_improved(barcode)
    
    combined = format_flight_number(parsed['carrier_code'], parsed['flight_number'])
    
    print(f"\nРезультаты:")
    print(f"  PNR: {parsed['PNR']}")
    print(f"  Origin: {parsed['origin_airport']}")
    print(f"  Dest: {parsed['destination_airport']}")
    print(f"  Carrier: {parsed['carrier_code']}")
    print(f"  Flight: {parsed['flight_number']}")
    print(f"  Combined: {combined}")
    
    print(f"\nОжидалось:")
    print(f"  PNR: {expected['pnr']}")
    print(f"  Origin: {expected['origin']}")
    print(f"  Dest: {expected['dest']}")
    print(f"  Combined: {expected['combined']}")
    
    errors = []
    if parsed['PNR'] != expected['pnr']:
        errors.append(f"PNR: получено '{parsed['PNR']}', ожидалось '{expected['pnr']}'")
    if parsed['origin_airport'] != expected['origin']:
        errors.append(f"Origin: получено '{parsed['origin_airport']}', ожидалось '{expected['origin']}'")
    if parsed['destination_airport'] != expected['dest']:
        errors.append(f"Dest: получено '{parsed['destination_airport']}', ожидалось '{expected['dest']}'")
    if combined != expected['combined']:
        errors.append(f"Combined: получено '{combined}', ожидалось '{expected['combined']}'")
    
    if errors:
        print(f"\n❌ ПРОВАЛЕН:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(f"\n✅ ПРОЙДЕН")
        return True


def main():
    print("="*80)
    print("ФИНАЛЬНЫЙ ТЕСТ УЛУЧШЕННОГО ПАРСЕРА BCBP")
    print("="*80)
    
    tests = [
        {
            "barcode": "HDCBCRI#6M1HUSEYNOV/ILHAM      E2OF95Y OSSBSZMN 0006 339Y011A0001 100",
            "expected": {
                "pnr": "E2OF95Y",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "barcode": "HDCBCRI#6M1SAKMATOV/MARISH EOANENY OSSBSZMN 0006 339Y018C0001 100",
            "expected": {
                "pnr": "EOANENY",
                "origin": "OSS",
                "dest": "BSZ",
                "combined": "MN06"
            }
        },
        {
            "barcode": "HDCBCRI#6M1KADYRKULOV/KANATBEK EOQRHJ8 OSSBSZMN 0006 339Y016B0001 100",
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
        success = test_case(i, test["barcode"], test["expected"])
        results.append(success)
    
    print(f"\n{'='*80}")
    print("ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'='*80}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Всего тестов: {total}")
    print(f"Успешно: {passed}")
    print(f"Провалено: {total - passed}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\nУлучшенный парсер готов к применению в scanner_websocket_bridge.py")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) провалено.")
        return 1


if __name__ == "__main__":
    exit(main())
