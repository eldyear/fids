from app.models import InfTablo
from django.shortcuts import render, redirect, get_object_or_404
from .models import Flight, Container, Baggage
import datetime
from datetime import date
from django.db import transaction
import re
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required

from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from django.http import HttpResponse
from django.db.models import Q

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def login_view(request):
    if request.method == 'POST':
        # Создаем форму, заполненную данными из POST-запроса
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            # Если форма валидна, входим в систему
            user = form.get_user()
            login(request, user)
            
            # Перенаправляем на страницу списка рейсов после успешного входа
            return redirect('flight_list') 
    else:
        # Для GET-запроса (первое открытие страницы) создаем пустую форму
        form = AuthenticationForm()
        
    return render(request, 'barbag/login.html', {'form': form})

def logout_view(request):
    logout(request)
    # Перенаправляем обратно на страницу входа
    return redirect('login') 

@login_required(login_url='login')
def flight_list(request):
    selected_date_str = request.GET.get('date')
    search_query = request.GET.get('query', '').strip()

    if selected_date_str:
        selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    else:
        selected_date = datetime.date.today()
    
    # 1. ФИЛЬТРАЦИЯ ПО АВИАКОМПАНИЯМ И ДАТЕ
    allowed_airlines = ['FV', 'DP', 'SU']
    
    flights = InfTablo.objects.filter(
        direction='dep', 
        date1=selected_date,
        airline__in=allowed_airlines 
    )

    # 2. ИСПРАВЛЕНИЕ: ДОБАВЛЕНИЕ ПОИСКА ПО QUERY (НОМЕР РЕЙСА ИЛИ НАПРАВЛЕНИЕ)
    if search_query:
        from django.db.models import Q
        # Используем Q-объекты для поиска по номеру рейса ИЛИ направлению
        flights = flights.filter(
            Q(flight__icontains=search_query) | Q(destination__icontains=search_query)
        )

    for flight in flights:
        # Check if a corresponding flight exists in the Flight model
        # We assume flight_num is the common key between InfTablo and Flight
        corresponding_flight_instance = Flight.objects.filter(flight_num=flight.flight, date_planned=flight.date1).first()

        has_baggage = False
        # В InfTablo поле 'airline' содержит код, используем его для сравнения
        if corresponding_flight_instance:
            # Теперь мы используем instance Flight, чтобы проверить наличие багажа
            has_baggage = Baggage.objects.filter(container__flight=corresponding_flight_instance).exists()
        
        flight.is_ready_for_details = has_baggage
    
    context = {
        'flights': flights,
        'selected_date': selected_date,
        'search_query': search_query,
    }
    
    return render(request, 'barbag/flight_list.html', context)


@login_required(login_url='login')
def select_flight(request):
    if request.method == 'POST':
        # Получаем ID рейса из POST-запроса
        fids_flight_id = request.POST.get('flight_id')
        
        # Находим рейс в базе данных FIDS по его ID
        try:
            # Исправлено: теперь используем 'pk' или 'id'
            fids_flight = InfTablo.objects.get(pk=fids_flight_id)
            
            # Копируем нужные данные в вашу новую модель Flight
            flight, created = Flight.objects.get_or_create(
                flight_id=fids_flight.id, # Используем ID из FIDS
                defaults={
                    'direction': fids_flight.direction,
                    'airline': fids_flight.airline,
                    'flight_num': fids_flight.flight,
                    'destination': fids_flight.destination,
                    'date_planned': fids_flight.date1,
                    'time_planned': fids_flight.time1,
                }
            )
            
            # Перенаправляем на страницу сканирования с ID созданного рейса
            return redirect('scan_baggage', flight_id=flight.id)
            
        except InfTablo.DoesNotExist:
            return render(request, 'barbag/error.html', {'message': 'Рейс не найден.'})
            
    return redirect('flight_list')


@login_required(login_url='login')
def scan_baggage(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    baggage_limit = 30
    error = None
    success_message = None
    
    if request.method == 'POST':
        scanned_barcode_raw = request.POST.get('barcode')
        
        if not scanned_barcode_raw:
            pass 
        else:
            scanned_barcode_raw = scanned_barcode_raw.strip()
            is_container = scanned_barcode_raw.lower().startswith('container')

            with transaction.atomic():
                # Ищем активный контейнер ДЛЯ ЭТОГО РЕЙСА (нужен для всех блоков)
                current_active_container = Container.objects.filter(flight=flight, is_closed=False).first()
                
                if is_container:
                    # =================================================================
                    # !!! БЛОК 1: ОБРАБОТКА КОНТЕЙНЕРА (ОТКРЫТИЕ/ЗАКРЫТИЕ) !!!
                    # =================================================================
                    
                    # 1. ЛОГИКА ЗАКРЫТИЯ (ДВОЙНОЕ СКАНИРОВАНИЕ)
                    if current_active_container and current_active_container.barcode.lower() == scanned_barcode_raw.lower():
                        current_active_container.is_closed = True
                        current_active_container.save()
                        success_message = f'Контейнер {current_active_container.barcode} успешно закрыт (двойное сканирование). Всего багажа: {current_active_container.baggage_count}.'
                        # Сброс ссылки на закрытый контейнер
                        current_active_container = None
                    
                    else:
                        # 2. АКТИВАЦИЯ/ПЕРЕИСПОЛЬЗОВАНИЕ НОВОГО КОНТЕЙНЕРА
                        
                        # Шаг A: Закрываем предыдущий активный контейнер ТЕКУЩЕГО РЕЙСА
                        if current_active_container and current_active_container.baggage_count > 0:
                            current_active_container.is_closed = True
                            current_active_container.save()
                            success_message = f'Предыдущий контейнер {current_active_container.barcode} успешно закрыт. Всего багажа: {current_active_container.baggage_count}.'
                        
                        # Шаг B: Ищем или создаем контейнер для активации
                        container_to_activate = Container.objects.filter(
                            barcode=scanned_barcode_raw,
                            flight=flight
                        ).first()
                        
                        if container_to_activate:
                            if container_to_activate.is_closed:
                                container_to_activate.is_closed = False
                                container_to_activate.save()
                                success_message = f'Контейнер {container_to_activate.barcode} повторно активирован для рейса {flight.flight_num}.'
                            else:
                                success_message = f'Контейнер {container_to_activate.barcode} уже активен.'
                        else:
                            container_to_activate = Container.objects.create(
                                barcode=scanned_barcode_raw,
                                flight=flight,
                                is_closed=False, 
                                baggage_count=0 
                            )
                            success_message = f'Новый экземпляр контейнера {container_to_activate.barcode} создан и активирован для рейса {flight.flight_num}.'
                            
                        # Устанавливаем ссылку на только что активированный/созданный контейнер
                        current_active_container = container_to_activate 
                
                else: 
                    # =================================================================
                    # !!! БЛОК 2: ОБРАБОТКА БАГАЖА !!!
                    # =================================================================
                    
                    # Проверка наличия активного контейнера (КРИТИЧНАЯ ПРОВЕРКА!)
                    if not current_active_container:
                        error = 'Нет активных контейнеров. Сначала отсканируйте контейнер.'
                    elif current_active_container.baggage_count >= baggage_limit:
                        error = 'Контейнер заполнен. Отсканируйте новый контейнер.'
                    else:
                        scanned_barcode = re.sub(r'[^0-9]', '', scanned_barcode_raw)
                        
                        # ЛОГИКА ПРОВЕРКИ ДАВНОСТИ БАГАЖА (остается без изменений)
                        from datetime import timedelta
                        from django.utils import timezone 
                        
                        six_months_ago = timezone.now() - timedelta(days=180)

                        existing_baggage = Baggage.objects.filter(
                            barcode=scanned_barcode,
                            scanned_at__gte=six_months_ago 
                        ).first()

                        if existing_baggage:
                            # Проверяем, не сканируется ли тот же багаж снова в ТОТ ЖЕ активный контейнер
                            if existing_baggage.container == current_active_container:
                                error = f'Багаж с номером {scanned_barcode} уже в этом контейнере.'
                            else:
                                flight_num = existing_baggage.container.flight.flight_num
                                error = f'Багаж с номером {scanned_barcode} уже был отсканирован для рейса {flight_num} и считается актуальным (менее 6 месяцев).'
                        
                        else:
                            try:
                                airline_code = scanned_barcode[0:3]
                                baggage_num = scanned_barcode[3:9]
                                destination_code = scanned_barcode[9:]
                            except IndexError:
                                error = 'Неверный формат штрихкода багажа.'
                            
                            if not error:
                                Baggage.objects.create(
                                    barcode=scanned_barcode,
                                    container=current_active_container,
                                    baggage_num=baggage_num,
                                    airline_code=airline_code,
                                    destination_code=destination_code,
                                )
                                current_active_container.baggage_count += 1
                                current_active_container.save()
                                success_message = f'Багаж {scanned_barcode} успешно добавлен.'
                                    
    # КОНТЕКСТ:
    # Получаем все контейнеры для данного рейса
    all_flight_containers = Container.objects.filter(flight=flight)

    # Активные контейнеры
    open_containers = all_flight_containers.filter(is_closed=False).order_by('last_scanned_at')
    
    # Общее количество багажа в рейсе
    total_baggage_count = Baggage.objects.filter(container__in=all_flight_containers).count() # <-- NEW

    # Список последних отсканированных багажей для ВСЕХ контейнеров рейса
    scanned_baggage_list = Baggage.objects.filter(container__flight=flight).order_by('-scanned_at')[:7] # <-- IMPROVED

    context = {
        'flight': flight,
        'open_containers': open_containers,
        'scanned_baggage_list': scanned_baggage_list,
        'total_baggage_count': total_baggage_count, # <-- NEW
        'error': error,
        'success_message': success_message,
    }

    return render(request, 'barbag/scan_baggage.html', context)


@login_required(login_url='login')
def search_baggage(request):
    """
    Обрабатывает поисковый запрос и отображает результаты по части штрихкода.
    """
    baggage_list = []
    search_query = request.GET.get('barcode', '').strip()

    if search_query:
        # Ищем багаж, где штрихкод содержит введенную строку
        baggage_list = Baggage.objects.filter(barcode__icontains=search_query)
    
    context = {
        'baggage_list': baggage_list,
        'search_query': search_query
    }
    return render(request, 'barbag/search_baggage.html', context)


@login_required(login_url='login')
def flight_details(request, flight_id):
    flight = get_object_or_404(Flight, flight_id=flight_id)
    containers = Container.objects.filter(flight=flight).order_by('-is_closed', 'barcode')

    if request.method == 'POST':
        total_weight_str = request.POST.get('total_weight')
        try:
            total_weight = float(total_weight_str)
            flight.total_weight = total_weight
            flight.save()
        except (ValueError, TypeError):
            pass

    total_baggage_count = Baggage.objects.filter(container__in=containers).count()
    average_weight = None
    if flight.total_weight and total_baggage_count > 0:
        average_weight = flight.total_weight / total_baggage_count

    average_weight_per_container = None
    total_containers_count = containers.count()
    if flight.total_weight and total_containers_count > 0:
        average_weight_per_container = flight.total_weight / total_containers_count

    # Вычисляем примерный вес для каждого контейнера
    for container in containers:
        container.baggage_list = Baggage.objects.filter(container=container).order_by('scanned_at')
        if average_weight:
            container.estimated_weight = container.baggage_count * average_weight
        else:
            container.estimated_weight = None

    context = {
        'flight': flight,
        'containers': containers,
        'total_baggage_count': total_baggage_count,
        'average_weight': average_weight,
        'average_weight_per_container': average_weight_per_container,
    }
    return render(request, 'barbag/flight_details.html', context)


# @login_required(login_url='login')
def generate_pdf_report(request, flight_id):
    """
    Генерирует PDF-отчет для выбранного рейса.
    """
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        pdfmetrics.registerFontFamily('DejaVuSans', normal='DejaVuSans', bold='DejaVuSans', italic='DejaVuSans', boldItalic='DejaVuSans')
    except Exception as e:
        print(f"Ошибка при регистрации шрифта: {e}")
        return HttpResponse("Ошибка сервера: не удалось загрузить шрифт.", status=500)
    
    # Ищем рейс по полю flight_id, а не по pk
    flight = get_object_or_404(Flight, flight_id=flight_id)
    containers = Container.objects.filter(flight=flight).order_by('-is_closed', 'barcode')

    # Расчеты для отчета
    total_baggage_count = Baggage.objects.filter(container__in=containers).count()
    average_weight = None
    if flight.total_weight and total_baggage_count > 0:
        average_weight = flight.total_weight / total_baggage_count

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = 'DejaVuSans'
    styles['h1'].fontName = 'DejaVuSans'
    styles['h2'].fontName = 'DejaVuSans'
    
    # Добавляем информацию о рейсе
    elements.append(Paragraph(f"<b>Отчет по рейсу:</b> {flight.flight_num}", styles['h1']))
    elements.append(Paragraph(f"<b>Направление:</b> {flight.destination}", styles['Normal']))
    elements.append(Paragraph(f"<b>Дата вылета:</b> {flight.date_planned}", styles['Normal']))
    elements.append(Paragraph(f"<b>Время вылета:</b> {flight.time_planned}", styles['Normal']))
    elements.append(Paragraph(f"<b>Средний вес багажа:</b> {average_weight:.2f} кг" if average_weight else "<b>Средний вес багажа:</b> Не рассчитан", styles['Normal']))
    
    # Добавляем заголовок таблицы
    elements.append(Paragraph("<br/>", styles['Normal']))
    elements.append(Paragraph("<b>Сводка по контейнерам</b>", styles['h2']))

    # Данные для таблицы
    data = [['Имя контейнера', 'Количество багажа', 'Примерный вес (кг)']]
    for container in containers:
        estimated_weight = container.baggage_count * average_weight if average_weight else 'Не рассчитан'
        data.append([
            container.barcode,
            container.baggage_count,
            f"{estimated_weight:.2f}" if isinstance(estimated_weight, (int, float)) else estimated_weight
        ])

    table_style = TableStyle([
        # ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        # ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    
    table = Table(data)
    table.setStyle(table_style)
    elements.append(table)

    doc.build(elements)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="report_{flight.flight_num}.pdf"' # <--- ВОТ ИЗМЕНЕНИЕ
    response.write(buffer.getvalue())
    buffer.close()
    return response

@login_required(login_url='login')
def close_container(request, container_id):
    """
    Обрабатывает запрос на закрытие активного контейнера.
    """
    container = get_object_or_404(Container, pk=container_id)
    flight_id = container.flight.id
    
    # Только POST-запросы должны закрывать контейнер
    if request.method == 'POST':
        with transaction.atomic():
            container.is_closed = True
            container.save()
            
            # Дополнительное сообщение об успехе, которое можно передать через сессию
            # Но для простоты пока просто редиректим
            
            return redirect('scan_baggage', flight_id=flight_id)
            
    # Если это GET-запрос, просто возвращаем пользователя на страницу сканирования
    return redirect('scan_baggage', flight_id=flight_id)