from django.shortcuts import render

# billing_api/views.py

import requests
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from urllib.parse import urlencode

@require_http_methods(["GET"])
def get_billing_data(request):
    """
    Отправляет GET-запрос к billing.csp и возвращает JSON-ответ.
    """
    base_url = "http://199.1.1.1/csp/adp/japibilling.csp"
    
    # Получаем параметры фильтрации из GET-запроса
    params = request.GET.dict()
    
    # Формируем полный URL с параметрами
    full_url = f"{base_url}?{urlencode(params)}"
    
    try:
        # Отправляем HTTP-запрос
        response = requests.get(full_url, headers={"Accept": "application/json"})
        response.raise_for_status()  # Вызовет исключение для ошибок HTTP
        print("Response content:", response.text)
        # Парсим JSON-ответ
        data = response.json()
        
        # Возвращаем JSON-ответ
        return JsonResponse(data, safe=False)
        
    except requests.exceptions.RequestException as e:
        # Обрабатываем ошибки, связанные с HTTP-запросом
        return JsonResponse({"error": str(e)}, status=500)
    except json.JSONDecodeError as e:
        # Обрабатываем ошибки парсинга JSON
        return JsonResponse({"error": "Failed to decode JSON response from source."}, status=500)