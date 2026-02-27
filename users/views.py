# Стандартные библиотеки
import json
from datetime import datetime, timedelta, date

# Django импорты
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views import View
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator

from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.generic.edit import FormView

# Локальные импорты
from app.models import InfTablo, Status, FlightTemplate, DIRECTION, FlightForTemplate, Airline, Cities, Gates, Stoiki
from .forms import InfTabloForm, DateFilterForm, SelectDateForm, FlightTemplateForm, FlightForTemplateForm
from .api_importer import import_flights_from_api

# Общие переменные
today = datetime.today().date()
tomorrow = today + timedelta(days=1)


# Авторизация
def login_view(request):
    # Если пользователь уже авторизован, перенаправляем его
    if request.user.is_authenticated:
        return redirect('user_menu')  # Перенаправление на "user_menu"

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Вы успешно вошли в систему.")

            # Перенаправление на страницу из параметра "next" или на "user_menu"
            next_url = request.GET.get('next', 'user_menu')
            return redirect(next_url)
        else:
            messages.error(request, "Неверный логин или пароль.")
    else:
        form = AuthenticationForm()

    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, "Вы успешно вышли из системы.")
    return redirect('login')


# Управление рейсами
class BaseInfTabloView(SuccessMessageMixin):
    model = InfTablo
    form_class = InfTabloForm
    success_url = reverse_lazy('inftablo_list')
    success_message = "Информация успешно сохранена!"


class InfTabloListView(LoginRequiredMixin, BaseInfTabloView, ListView):
    template_name = 'users/flight_list.html'
    context_object_name = 'inftablos'

    login_url = '/users/'
    redirect_field_name = 'next'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        # Date persistence logic:
        # 1. Check GET parameter (user explicitly selected)
        # 2. Check session (previously selected)
        # 3. Default to today

        selected_date_str = self.request.GET.get('selected_date')

        if selected_date_str:
            # User explicitly selected a date
            try:
                filter_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                # Save to session
                self.request.session['selected_date'] = selected_date_str
            except ValueError:
                filter_date = today
        elif 'selected_date' in self.request.session:
            # Use previously selected date from session
            try:
                filter_date = datetime.strptime(self.request.session['selected_date'], '%Y-%m-%d').date()
            except (ValueError, KeyError):
                filter_date = today
        else:
            # Default to today
            filter_date = today
            self.request.session['selected_date'] = filter_date.strftime('%Y-%m-%d')

        # Определяем направление
        direction = self.request.GET.get('direction', 'dep')

        # Фильтруем записи
        departures = InfTablo.objects.filter(direction='dep', date1=filter_date).order_by('date1', 'time1')
        arrivals = InfTablo.objects.filter(direction='arr', date1=filter_date).order_by('date1', 'time1')

        if direction == 'arr':
            context['arrivals'] = arrivals
        else:
            context['departures'] = departures

        # Добавляем данные в контекст
        form = DateFilterForm(initial={'selected_date': filter_date})
        context.update({
            'form': form,
            'status_choices': Status.objects.all(),
            'direction': direction,
            'todays_date': today,
            'selected_date': filter_date.strftime('%Y-%m-%d'),
            'all_gates': Gates.objects.all(),
            'all_desks': Stoiki.objects.all(),
        })
        return context

def search_flights(request):
    query = request.GET.get('q')  # Получаем поисковый запрос из GET-параметров
    results = []

    if query:
        results = InfTablo.objects.filter(
            Q(flight__flights__icontains=query) | Q(destination__city_name_ru__icontains=query)
        ).select_related('destination', 'flight').order_by('date1', 'time1')

    context = {
        'query': query,
        'results': results,
    }
    return render(request, 'user_templates/search_results.html', context)

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from collections import defaultdict
@login_required(login_url='/users/')  # Гарантирует, что доступ к user_menu возможен только после вход

def user_menu(request):
    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    next_month_start = (current_month_start + timezone.timedelta(days=32)).replace(day=1)

    flights_by_city = InfTablo.objects.filter(
        date1__gte=current_month_start,
        date1__lt=next_month_start
    ).values('destination__city_name_ru', 'destination__city_name_en', 'direction').annotate(num_flights=Count('id'))

    city_data = {}
    all_cities = {}  # Changed to dict to store both translations

    for item in flights_by_city:
        city_ru = item['destination__city_name_ru']
        city_en = item['destination__city_name_en'] or city_ru  # Fallback to RU if EN is null
        direction = item['direction']
        count = item['num_flights']

        if city_ru not in all_cities:
            all_cities[city_ru] = city_en

        if city_ru not in city_data:
            city_data[city_ru] = {'arrivals': 0, 'departures': 0}
        if direction == 'arr':
            city_data[city_ru]['arrivals'] += count
        elif direction == 'dep':
            city_data[city_ru]['departures'] += count

    cities_ru = sorted(list(all_cities.keys()))
    cities_en = [all_cities[city] for city in cities_ru]
    departure_counts = [city_data[city]['departures'] for city in cities_ru]
    arrival_counts = [city_data[city]['arrivals'] for city in cities_ru]

    airline_flights = InfTablo.objects.filter(
        date1__gte=current_month_start,
        date1__lt=next_month_start
    ).values('airline').annotate(num_flights=Count('id')).order_by('-num_flights')

    airlines = [item['airline'] for item in airline_flights]
    flight_counts = [item['num_flights'] for item in airline_flights]

    # Generate dynamic colors for cities
    city_colors = {}
    for i, city in enumerate(cities_ru):
        r = (i * 50) % 256
        g = (i * 100) % 256
        b = (i * 150) % 256
        city_colors[city] = f'rgba({r}, {g}, {b}, 0.7)'

    city_color_list = [city_colors[city] for city in cities_ru]

    # Today's stats
    today_flights = InfTablo.objects.filter(date1=today)
    total_today = today_flights.count()
    departures_today = today_flights.filter(direction='dep').count()
    arrivals_today = today_flights.filter(direction='arr').count()

    # Active gates (flights with gates assigned for today)
    active_gates = today_flights.exclude(gate=None).values('gate').distinct().count()

    # Status counts
    from django.db.models import Q
    status_counts = {
        'on_time': today_flights.filter(Q(status__name_en__icontains='scheduled') | Q(status__name_en__icontains='on time')).count(),
        'delayed': today_flights.filter(status__name_en__icontains='delay').count(),
        'boarding': today_flights.filter(status__name_en__icontains='boarding').count(),
        'departed': today_flights.filter(status__name_en__icontains='departed').count(),
        'arrived': today_flights.filter(status__name_en__icontains='arrived').count(),
        'cancelled': today_flights.filter(status__name_en__icontains='cancel').count(),
    }

    context = {
        'cities': json.dumps(cities_ru),
        'cities_en': json.dumps(cities_en),
        'departure_counts_by_city': json.dumps(departure_counts),
        'arrival_counts_by_city': json.dumps(arrival_counts),
        'city_colors': json.dumps(city_color_list),
        'airline_labels_current_month': json.dumps(airlines),
        'airline_data_current_month': json.dumps(flight_counts),
        # Today's stats
        'total_flights_today': total_today,
        'departures_today': departures_today,
        'arrivals_today': arrivals_today,
        'active_gates_count': active_gates,
        'status_on_time': status_counts['on_time'],
        'status_delayed': status_counts['delayed'],
        'status_boarding': status_counts['boarding'],
        'status_departed': status_counts['departed'],
        'status_arrived': status_counts['arrived'],
        'status_cancelled': status_counts['cancelled'],
    }
    return render(request, 'users/home.html', context)


class InfTabloCreateView(LoginRequiredMixin, BaseInfTabloView, CreateView):
    template_name = 'users/inftablo_form.html'

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')


class InfTabloUpdateView(LoginRequiredMixin, BaseInfTabloView, UpdateView):
    template_name = 'users/inftablo_form.html'

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')

    def form_valid(self, form):
        if 'save_as_new' in self.request.POST:
            form.instance.pk = None
            form.instance.id = None
        return super().form_valid(form)

class InfTabloDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = InfTablo
    template_name = 'users/inftablo_confirm_delete.html'
    success_message = "Рейс успешно удалён!"
    login_url = '/users/'
    redirect_field_name = 'next'

    def get_success_url(self):
        # Preserve filters when redirecting back
        direction = self.request.GET.get('direction', 'dep')
        selected_date = self.request.GET.get('selected_date', '')

        base_url = reverse('inftablo_list')
        params = []
        if direction:
            params.append(f'direction={direction}')
        if selected_date:
            params.append(f'selected_date={selected_date}')

        if params:
            return f'{base_url}?{"&".join(params)}'
        return base_url

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


@csrf_protect
def update_status(request):
    if request.method == 'POST':
        inftablo_id = request.POST.get("inftablo_id")
        status_id = request.POST.get("status_id")
        selected_date = request.POST.get("selected_date")
        direction = request.POST.get("direction")

        print(f"Значение selected_date при обновлении статуса: {selected_date}")
        print(f"Значение direction при обновлении статуса: {direction}")

        try:
            inftablo = get_object_or_404(InfTablo, id=inftablo_id)
            if status_id:
                new_status = get_object_or_404(Status, id=status_id)
                inftablo.status = new_status
            else:
                inftablo.status = None
            inftablo.save()

            # Формируем URL для перенаправления с параметрами из POST
            redirect_url = reverse('inftablo_list')
            params = []
            if direction:
                params.append(f'direction={direction}')
            if selected_date:
                params.append(f'selected_date={selected_date}')

            if params:
                redirect_url += '?' + '&'.join(params)

            return redirect(redirect_url)

        except (InfTablo.DoesNotExist, Status.DoesNotExist):
            return redirect('inftablo_list') # Или обработайте ошибку как вам нужно

    # Если метод не POST, просто перенаправляем на список (обычно не должно происходить)
    return redirect('inftablo_list')


@login_required(login_url='/users/')
def generate_daily_schedule_view(request):
    if request.method == "POST":
        form = SelectDateForm(request.POST)
        if form.is_valid():
            selected_date = form.cleaned_data.get('date') or timezone.now().date()
            selected_day = selected_date.weekday() + 1

            templates = FlightTemplate.objects.filter(
                season_start__lte=selected_date,
                season_end__gte=selected_date,
                weekdays__contains=str(selected_day)
            )

            created_count = 0
            for template in templates:
                if not InfTablo.objects.filter(flight=template.flight.flight, date1=selected_date).exists():
                    InfTablo.objects.create(
                        direction=template.direction,
                        airline=template.flight.airline,
                        flight=template.flight.flight,
                        destination=template.flight.destination,
                        date1=selected_date,
                        time1=template.time
                    )
                    created_count += 1

            messages.success(request, f"Сформировано {created_count} рейсов на {selected_date}.")
            return redirect('inftablo_list')
    else:
        form = DateFilterForm(initial={'date': timezone.now().date()})

    return render(request, "users/generate_daily_schedule.html", {"form": form})


# Шаблоны рейсов
class FlightTemplateListView(LoginRequiredMixin, ListView):
    model = FlightTemplate
    template_name = 'users/flight_template_list.html'
    context_object_name = 'flight_templates'
    paginate_by = 10

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')


class FlightTemplateCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = FlightTemplate
    form_class = FlightTemplateForm
    template_name = 'users/flight_template_form.html'
    success_url = reverse_lazy('flight_template_list')
    success_message = "Шаблон успешно создан!"

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')

    def get_initial(self):
        initial = super().get_initial()
        last_template = FlightTemplate.objects.order_by('-id').first()
        if last_template:
            initial.update({
                'season_start': last_template.season_start,
                'season_end': last_template.season_end,
            })
        return initial


class FlightTemplateUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = FlightTemplate
    form_class = FlightTemplateForm
    template_name = 'users/flight_template_form.html'
    success_url = reverse_lazy('flight_template_list')
    success_message = "Шаблон успешно обновлён!"

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')


class FlightTemplateDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = FlightTemplate
    template_name = 'users/flight_template_confirm_delete.html'
    success_url = reverse_lazy('flight_template_list')
    success_message = "Шаблон успешно удалён!"

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')






class InfTabloCombinedView(LoginRequiredMixin, BaseInfTabloView, ListView):
    model = InfTablo
    template_name = 'user_templates/inftablo_combined.html'
    context_object_name = 'inftablos'

    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')

    def get_queryset(self):
        return InfTablo.objects.all()

    def get_filter_date(self):
        today = timezone.now().date()
        date_filter_form = DateFilterForm(self.request.GET)
        if date_filter_form.is_valid() and date_filter_form.cleaned_data['selected_date']:
            return date_filter_form.cleaned_data['selected_date']
        return today

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_date = self.get_filter_date()
        direction = self.request.GET.get('direction')

        departures = InfTablo.objects.filter(direction='dep', date1=filter_date).order_by('date1', '-time1')
        arrivals = InfTablo.objects.filter(direction='arr', date1=filter_date).order_by('date1', '-time1')

        context['departures'] = departures if direction != 'arr' else None
        context['arrivals'] = arrivals if direction != 'dep' else None
        context.update({
            'date_filter_form': DateFilterForm(self.request.GET),
            'inftablo_form': InfTabloForm(),
            'status_choices': Status.objects.all(),
            'direction': direction,
        })
        return context

    def process_form(self, request):
        pk = request.POST.get('pk')
        if not pk:
            form = InfTabloForm(request.POST)
        else:
            try:
                instance = InfTablo.objects.get(pk=pk)
                form = InfTabloForm(request.POST, instance=instance)
            except (InfTablo.DoesNotExist, ValueError):
                return {'success': False, 'errors': 'Рейс не найден'}

        if form.is_valid():
            form.save()
            return {'success': True, 'message': 'Рейс успешно сохранен'}
        return {'success': False, 'errors': form.errors}

    def post(self, request, *args, **kwargs):
        response = self.process_form(request)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response)
        return redirect('inftablo_combined')

    def get_form(self, pk=None):
        """
        Возвращает форму InfTabloForm.
        Если указан pk, возвращает форму с объектом (для редактирования),
        иначе возвращает пустую форму (для создания нового объекта).
        """
        if pk:
            try:
                instance = InfTablo.objects.get(pk=pk)
                form = InfTabloForm(instance=instance)
                return form
            except (InfTablo.DoesNotExist, ValueError):
                return None
        return InfTabloForm()

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 'pk' in request.GET:
            form = self.get_form(request.GET.get('pk'))
            if form:
                form_html = render_to_string('partials/form.html', {'form': form}, request=request)
                return JsonResponse({'form_html': form_html})
            return JsonResponse({'error': 'Рейс не найден.'}, status=404)
        return super().get(request, *args, **kwargs)


from django.views.generic.edit import CreateView
from django.urls import reverse_lazy

class FlightForTemplateCreateView(LoginRequiredMixin, CreateView):
    model = FlightForTemplate
    form_class = FlightForTemplateForm
    template_name = 'user_templates/flight_create.html'  # Указываем шаблон
    # fields = ['airline', 'flight', 'destination']  # Поля, которые будут отображаться в форме
    success_url = reverse_lazy('add_flights')
    login_url = '/users/'  # Укажите URL страницы входа (опционально)
    redirect_field_name = 'next'  # Параметр, куда сохраняется исходный URL (по умолчанию 'next')


# export to docx

from django.http import HttpResponse
from django.utils.timezone import now
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Mm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from app.models import InfTablo
from .forms import SelectDateForm
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta

@login_required(login_url='/users/')
def export_daily_plan_to_docx(request):
    # Получаем текущую дату (на случай, если ничего не выбрано)
    today = now().date()

    # Получаем дату из формы
    form = SelectDateForm(request.GET)
    filter_date = today
    if form.is_valid():
        filter_date = form.cleaned_data['selected_date']

    # Определяем направление
    direction = request.GET.get('direction', 'dep')

    # Фильтруем данные
    if direction == 'arr':
        tablo_entries = InfTablo.objects.filter(direction='arr', date1=filter_date).order_by('time1')
        direction_name = "Прилеты"
    else:
        tablo_entries = InfTablo.objects.filter(direction='dep', date1=filter_date).order_by('time1')
        direction_name = "Вылеты"

    # Создаём Word-документ
    document = Document()

    # Форматируем дату в формате dd.month.yyyy
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    formatted_date = f"{filter_date.day} {months[filter_date.month]} {filter_date.year}"

    # Заголовок документа
    heading = document.add_heading(f'Суточный план полетов аэропорта Ош на {formatted_date} ({direction_name})', level=1)

    # Добавляем отступ после заголовка
    paragraph = document.add_paragraph()  # Создаем пустой абзац для отступа
    paragraph.add_run("")  # Добавляем пробел для пустого места

    # Устанавливаем формат A4 и альбомную ориентацию
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Mm(297)
    section.page_height = Mm(210)

    # Настраиваем поля страницы
    section.left_margin = Mm(15)
    section.right_margin = Mm(15)
    section.top_margin = Mm(20)
    section.bottom_margin = Mm(20)

    # Добавляем таблицу
    table = document.add_table(rows=1, cols=7)  # Увеличиваем количество столбцов
    table.style = 'Table Grid'

    # Применяем Times New Roman ко всему документу
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)  # Опционально: Установить размер шрифта
            r = run._element
            r.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')  # Для совместимости

    # Заголовки таблицы
    headers = ['Номер рейса', 'Направление', 'Время плановая', 'Время фактическая', 'Разница во времени', 'Статус', 'Примечание']
    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        cell = hdr_cells[i]
        cell.text = header

        # Форматируем шрифт заголовка таблицы
        cell_paragraph = cell.paragraphs[0]
        cell_paragraph.runs[0].bold = True  # Жирный шрифт
        cell_paragraph.runs[0].font.size = Pt(12)  # Размер шрифта

        # Устанавливаем фон ячеек заголовка
        shading_elm = OxmlElement("w:shd")  # Создаём элемент заливки
        shading_elm.set(qn("w:val"), "clear")  # Тип заливки
        shading_elm.set(qn("w:color"), "auto")  # Цвет текста
        shading_elm.set(qn("w:fill"), "D9D9D9")  # Цвет фона (светло-серый)

        # Добавляем элемент заливки в свойства ячейки
        tc_pr = cell._element.get_or_add_tcPr()
        tc_pr.append(shading_elm)

    # Заполняем таблицу данными
    for entry in tablo_entries:
        row_cells = table.add_row().cells
        row_cells[0].text = str(entry.flight) if entry.flight else '—'
        row_cells[1].text = str(entry.destination) if entry.destination else '—'
        row_cells[2].text = entry.time1.strftime('%H:%M') if entry.time1 else '—'
        row_cells[3].text = entry.last_time.strftime('%H:%M') if entry.last_time else '—'
        time_difference_str = ''

        if entry.time1 and entry.last_time:
            plan_datetime = datetime.combine(filter_date, entry.time1)
            fact_datetime = datetime.combine(filter_date, entry.last_time)
            diff = fact_datetime - plan_datetime
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            time_difference_str = f"{hours:+}ч {minutes:+}м"

        row_cells[4].text = time_difference_str
        # row_cells[5].text = entry.status.name if entry.status else '—'
        # row_cells[6].text = ', '.join([str(stoika) for stoika in entry.stoika.all()]) or '—'

        # Применяем Times New Roman к ячейкам данных
        for cell in row_cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)

    # Добавляем подпись
    document.add_paragraph(f'Дата экспорта: {now().strftime("%d.%m.%Y %H:%M")}')

    # Возвращаем файл в HTTP-ответе
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="daily_plan_{direction}_{filter_date}.docx"'
    document.save(response)
    return response

#export to EXCEL

import openpyxl
from django.http import HttpResponse
from django.utils.timezone import now
from .forms import SelectDateForm
from app.models import InfTablo
from django.contrib.auth.decorators import login_required
from datetime import datetime

@login_required(login_url='/users/')
def export_daily_plan_to_xlsx(request):
    # Получаем текущую дату
    today = now().date()

    # Получаем дату из формы
    form = SelectDateForm(request.GET)
    filter_date = today
    if form.is_valid():
        filter_date = form.cleaned_data['selected_date']

    # Определяем направление
    direction = request.GET.get('direction', 'dep')

    # Фильтруем данные
    if direction == 'arr':
        tablo_entries = InfTablo.objects.filter(direction='arr', date1=filter_date).order_by('time1')
        direction_name = "Прилеты"
    else:
        tablo_entries = InfTablo.objects.filter(direction='dep', date1=filter_date).order_by('time1')
        direction_name = "Вылеты"

    # Форматируем дату
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    formatted_date = f"{filter_date.day} {months[filter_date.month]} {filter_date.year}"

    # Создаем Excel-книгу и лист
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f'Суточный план ({direction_name}) на {formatted_date}' # Обновляем название листа

    # Добавляем заголовок в первую строку
    worksheet.append([f'Суточный план полетов аэропорта Ош на {formatted_date} ({direction_name})'])
    # Объединяем ячейки заголовка
    worksheet.merge_cells(f'A1:G1') # Предполагаем, что у вас 7 столбцов

    # Заголовки таблицы (начинаем со второй строки)
    headers = ['Номер рейса', 'Направление', 'Время плановая', 'Время фактическая', 'Разница во времени', 'Статус', 'Примечание']
    worksheet.append(headers)

    # Заполняем данными (начинаем с третьей строки)
    for entry in tablo_entries:
        plan_time_str = entry.time1.strftime('%H:%M') if entry.time1 else '—'
        fact_time_str = entry.last_time.strftime('%H:%M') if entry.last_time else '—'
        time_difference = ''

        if entry.time1 and entry.last_time:
            # Объединяем дату и время для корректного вычитания
            plan_datetime_str = f"{filter_date.strftime('%Y-%m-%d')} {entry.time1.strftime('%H:%M')}"
            fact_datetime_str = f"{filter_date.strftime('%Y-%m-%d')} {entry.last_time.strftime('%H:%M')}"

            try:
                plan_datetime = datetime.strptime(plan_datetime_str, '%Y-%m-%d %H:%M')
                fact_datetime = datetime.strptime(fact_datetime_str, '%Y-%m-%d %H:%M')
                diff = fact_datetime - plan_datetime
                total_seconds = int(diff.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                time_difference = f"{hours:+}ч {minutes:+}м"
            except ValueError:
                time_difference = 'Ошибка формата'

        worksheet.append([
            str(entry.flight) if entry.flight else '—',
            str(entry.destination) if entry.destination else '—',
            plan_time_str,
            fact_time_str,
            time_difference,
            # entry.status.name if entry.status else '—',
            # ', '.join([str(stoika) for stoika in entry.stoika.all()]) or '—',
        ])

    # Добавляем информацию о дате экспорта
    worksheet.append(['', '', '', '', '', '', f'Дата экспорта: {now().strftime("%d.%m.%Y %H:%M")}'])

    # Формируем HTTP-ответ
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="daily_plan_{direction}_{filter_date}.xlsx"'
    workbook.save(response)
    return response

#export to PDF

import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.http import HttpResponse
from django.utils.timezone import now
from .forms import SelectDateForm
from app.models import InfTablo
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta

# Зарегистрируйте шрифты DejaVu Sans
def _register_fonts():
    font_dir = os.path.join(os.path.dirname(__file__), '..', 'billing', 'static', 'fonts')
    try:
        dejavu_sans = os.path.join(font_dir, 'DejaVuSans.ttf')
        dejavu_bold = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')
        if os.path.exists(dejavu_sans):
            pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_sans))
        if os.path.exists(dejavu_bold):
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_bold))
    except Exception as e:
        print(f"Font registration warning: {e}")

_register_fonts()

# Use DejaVu Sans if available, otherwise fallback to standard fonts
default_font = 'DejaVuSans'
default_bold_font = 'DejaVuSans-Bold'


@login_required(login_url='/users/')
def export_daily_plan_to_pdf(request):
    # Получаем текущую дату
    today = now().date()

    # Получаем дату из формы
    form = SelectDateForm(request.GET)
    filter_date = today
    if form.is_valid():
        filter_date = form.cleaned_data['selected_date']

    # Определяем направление
    direction = request.GET.get('direction', 'dep')

    # Фильтруем данные и определяем название направления
    if direction == 'arr':
        tablo_entries = InfTablo.objects.filter(
            direction='arr', date1=filter_date).order_by('time1')
        direction_name = "Прилеты"
    else:
        tablo_entries = InfTablo.objects.filter(
            direction='dep', date1=filter_date).order_by('time1')
        direction_name = "Вылеты"

    # Форматируем дату
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    formatted_date = f"{filter_date.day} {months[filter_date.month]} {filter_date.year}"

    # Создаем PDF-документ
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="daily_plan_{direction}_{filter_date}.pdf"'
    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    style_heading = ParagraphStyle(
        name='HeadingDejaVu',
        parent=styles['h1'],
        fontName=default_font,
    )
    style_normal = ParagraphStyle(
        name='NormalDejaVu',
        parent=styles['Normal'],
        fontName=default_font,
        fontSize=10,
    )
    style_center = ParagraphStyle(
        name='CenterDejaVu',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontName=default_font,
        fontSize=10,
    )

    # Добавляем заголовок документа с направлением
    elements.append(
        Paragraph(f"Суточный план полетов аэропорта Ош на {formatted_date} ({direction_name})", style_heading))
    elements.append(Spacer(1, 12))

    # Заголовки таблицы
    table_data = [['Номер рейса', 'Направление', 'Время плановая', 'Время фактическая', 'Разница во времени', 'Статус', 'Примечание']]

    # Заполняем данные таблицы
    for entry in tablo_entries:
        time_difference_str = ''
        if entry.time1 and entry.last_time:
            plan_datetime = datetime.combine(filter_date, entry.time1)
            fact_datetime = datetime.combine(filter_date, entry.last_time)
            diff = fact_datetime - plan_datetime
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            time_difference_str = f"{hours:+}ч {minutes:+}м"

        table_data.append([
            Paragraph(str(entry.flight) if entry.flight else '—', style_center),
            Paragraph(str(entry.destination) if entry.destination else '—', style_center),
            Paragraph(entry.time1.strftime('%H:%M') if entry.time1 else '—', style_center),
            Paragraph(entry.last_time.strftime('%H:%M') if entry.last_time else '—', style_center),
            Paragraph(time_difference_str, style_center),
            # Paragraph(entry.status.name if entry.status else '—', style_normal),
            # Paragraph(', '.join([str(stoika) for stoika in entry.stoika.all()]) or '—', style_normal),
        ])

    # Определяем цвет заголовка
    header_color = colors.HexColor('#223142')

    # Базовый стиль таблицы
    base_style = [
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Выравниваем все ячейки по центру
        ('FONTNAME', (0, 0), (-1, 0), default_bold_font),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0, colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]

    # Стили для чередующихся строк
    row_styles = [
        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f2f2f2'))
        for i in range(1, len(table_data), 2)
    ]

    # Объединяем стили
    table_style = TableStyle(base_style + row_styles)

    # Создаем и добавляем таблицу
    table = Table(table_data)
    table.setStyle(table_style)
    elements.append(table)

    # Подпись
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(f'Дата экспорта: {now().strftime("%d.%m.%Y %H:%M")}', style_normal))

    doc.build(elements)
    return response

# API Import View
@login_required(login_url='/users/')
def import_flights_view(request):
    if request.method == "POST":
        date_str = request.POST.get('date')
        success, message = import_flights_from_api(date_str)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('inftablo_list')
    return redirect('inftablo_list')

# CRUD Views for Airlines, Cities, Gates, Desks

# Airlines
class AirlineListView(LoginRequiredMixin, ListView):
    model = Airline
    template_name = 'users/airline_list.html'
    context_object_name = 'airlines'
    paginate_by = 20

class AirlineCreateView(LoginRequiredMixin, CreateView):
    model = Airline
    fields = ['name', 'code', 'logo', 'svg_logo']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('airline_list')
    extra_context = {'title': 'Add Airline'}

class AirlineUpdateView(LoginRequiredMixin, UpdateView):
    model = Airline
    fields = ['name', 'code', 'logo', 'svg_logo']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('airline_list')
    extra_context = {'title': 'Edit Airline'}

# Cities
class CityListView(LoginRequiredMixin, ListView):
    model = Cities
    template_name = 'users/city_list.html'
    context_object_name = 'cities'
    paginate_by = 20

class CityCreateView(LoginRequiredMixin, CreateView):
    model = Cities
    fields = ['city_name_ru', 'city_name_en', 'city_name_ky', 'iata_code', 'icao_code']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('city_list')
    extra_context = {'title': 'Add City'}

class CityUpdateView(LoginRequiredMixin, UpdateView):
    model = Cities
    fields = ['city_name_ru', 'city_name_en', 'city_name_ky', 'iata_code', 'icao_code']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('city_list')
    extra_context = {'title': 'Edit City'}

# Gates
class GateListView(LoginRequiredMixin, ListView):
    model = Gates
    template_name = 'users/gate_list.html'
    context_object_name = 'gates'
    paginate_by = 20

class GateCreateView(LoginRequiredMixin, CreateView):
    model = Gates
    fields = ['gate']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('gate_list')
    extra_context = {'title': 'Add Gate'}

class GateUpdateView(LoginRequiredMixin, UpdateView):
    model = Gates
    fields = ['gate']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('gate_list')
    extra_context = {'title': 'Edit Gate'}

# Desks (Stoiki)
class DeskListView(LoginRequiredMixin, ListView):
    model = Stoiki
    template_name = 'users/desk_list.html'
    context_object_name = 'desks'
    paginate_by = 20

class DeskCreateView(LoginRequiredMixin, CreateView):
    model = Stoiki
    fields = ['stoiki', 'sky_priority']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('desk_list')
    extra_context = {'title': 'Add Desk'}

class DeskUpdateView(LoginRequiredMixin, UpdateView):
    model = Stoiki
    fields = ['stoiki', 'sky_priority']
    template_name = 'users/simple_form.html'
    success_url = reverse_lazy('desk_list')
    extra_context = {'title': 'Edit Desk'}

from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
@require_POST
def update_flight_inline(request, pk):
    try:
        flight = InfTablo.objects.get(pk=pk)

        # Helper to parse comma-separated IDs or Names (assuming Names for simplicity based on user request "2,3,4")
        # User said "enter desks comma separated", e.g. "2,3,4". These are likely the 'stoiki' field in Stoiki model.
        # Same for Gates ('gate' field in Gates model).

        def get_objects_from_string(model_class, field_name, input_str):
            if not input_str:
                return []
            values = [v.strip() for v in input_str.split(',') if v.strip()]
            objects = []
            for val in values:
                # Try to get exact match
                obj = model_class.objects.filter(**{field_name: val}).first()
                if obj:
                    objects.append(obj)
                # Optional: Create if not exists? User didn't explicitly ask, but for robustness:
                # obj, _ = model_class.objects.get_or_create(**{field_name: val})
                # objects.append(obj)
            return objects

        # Update Gates
        if 'gates' in request.POST:
            gates_str = request.POST.get('gates')
            gates_objs = get_objects_from_string(Gates, 'gate', gates_str)
            flight.gate.set(gates_objs)

        # Update Desks
        if 'desks' in request.POST:
            desks_str = request.POST.get('desks')
            desks_objs = get_objects_from_string(Stoiki, 'stoiki', desks_str)
            flight.stoika.set(desks_objs)

        # Update Status
        if 'status' in request.POST:
            status_id = request.POST.get('status')
            if status_id:
                try:
                    status = Status.objects.get(id=status_id)
                    flight.status = status
                    flight.save()
                except Status.DoesNotExist:
                    pass

        # Update Sky Priority Desks
        if 'sky_priority_desks' in request.POST:
            sp_desks_str = request.POST.get('sky_priority_desks')
            sp_desks_objs = get_objects_from_string(Stoiki, 'stoiki', sp_desks_str)
            flight.sky_priority_desks.set(sp_desks_objs)

        return JsonResponse({'status': 'success', 'message': 'Flight updated successfully'})
    except InfTablo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Flight not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)