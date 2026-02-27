from django import template

register = template.Library()

@register.filter
def get_number(stoika):
    # Предположим, что у вас есть поле name, содержащее строку типа "Стойка № 1"
    if hasattr(stoika, 'stoiki'):  # Проверяем, что поле существует
        return stoika.stoiki.split()[-1]  # Разделяем строку и возвращаем номер
    return ''