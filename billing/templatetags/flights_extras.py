# flights/templatetags/flights_extras.py

from django import template
from datetime import datetime, timedelta
from decimal import Decimal

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def duration_to(end_time, start_time):
    """
    Вычисляет разницу между двумя объектами времени и возвращает её в формате HH:MM.
    """
    if not end_time or not start_time:
        return "-"

    # Создаем объекты datetime, используя фиктивную дату, чтобы можно было вычесть
    dummy_date = datetime(2023, 1, 1)

    start_dt = datetime.combine(dummy_date, start_time)
    end_dt = datetime.combine(dummy_date, end_time)

    # Обрабатываем случай, если услуга длилась через полночь
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    duration = end_dt - start_dt

    total_seconds = duration.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)

    return f"{hours:02d}:{minutes:02d}"

# @register.filter
# def format_duration(duration):
#     if not duration:
#         return "-"
#     total_seconds = duration.total_seconds()
#     hours = int(total_seconds // 3600)
#     minutes = int((total_seconds % 3600) // 60)
#     return f"{hours:02d}:{minutes:02d}"

@register.filter
def decimal_to_period(value):
    """
    Форматирует десятичное число для использования в полях ввода типа number.
    Заменяет запятую на точку. Если число целое, убирает .00.
    """
    if value is None or value == '':
        return ''
    
    # Пытаемся преобразовать значение в Decimal
    try:
        dec_value = Decimal(str(value).replace(',', '.'))
        if dec_value == dec_value.to_integral_value():
            return str(int(dec_value))
        else:
            return str(dec_value).replace(',', '.')
    except (ValueError, TypeError):
        return str(value)
    
@register.filter(name='mul')
def mul(value, arg):
    """
    Фильтр для умножения.
    Использование: {{ value|mul:arg }}
    """
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return ''
    
@register.filter
def mod(value, arg):
    "Возвращает остаток от деления"
    try:
        return int(value) % int(arg)
    except (ValueError, TypeError):
        return ''

@register.filter(name='div')
def div(value, arg):
    """
    Фильтр для деления.
    Использование: {{ value|div:arg }}
    """
    try:
        return int(value) / int(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return ''

@register.filter(name='format_duration')
def format_duration(value):
    """
    Форматирует объект timedelta в строку "ЧЧч ММм".
    """
    if isinstance(value, timedelta):
        total_seconds = value.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}ч")
        if minutes > 0:
            parts.append(f"{minutes}м")
            
        return " ".join(parts)
    return ""
