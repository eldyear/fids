from django.contrib import admin
from django.utils.html import format_html
from .models import FlightNumber, Cities, Stoiki, InfTablo, Airline, Status, FlightTemplate, FlightForTemplate

admin.site.site_header = "Ош Аэропорт"
admin.site.site_title = "OSS admin"
admin.site.index_title = "Добро пожаловать в админ-панель"
admin.site.site_url = "/urls"


class InfTabloAdmin(admin.ModelAdmin):
    list_display = ('direction', 'flight', 'destination', 'get_destination_iata_code', 'date1', 'time1', 'last_date', 'last_time', 'status')
    list_display_links = ('flight',)
    search_fields = ('direction', 'flight__flights', 'destination__city_name_ru', 'airline__name', 'date1', 'time1', 'last_date', 'last_time', 'status__name_ru', 'stoika__stoiki')
    list_filter = ('direction', 'flight', 'destination', 'airline', 'date1')
    list_editable = ('last_time', 'status', 'date1')

    def get_destination_iata_code(self, obj):
        return obj.destination.iata_code

    def get_status_display(self, obj):
        if obj.status:
            return obj.status.name_ru
        return 'Не указан'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "flight":
            kwargs["queryset"] = FlightNumber.objects.all().order_by('flights')  # Упорядочиваем по коду рейса
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    get_destination_iata_code.short_description = 'IATA код'
    get_status_display.short_description = 'Статус'


from django.utils.timezone import now
from datetime import datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from .forms import SelectDateForm
from django.urls import path

class FlightTemplateAdmin(admin.ModelAdmin):
    """
    Кастомная админка для управления шаблонами рейсов.
    """
    list_display = ('flight', 'season_start', 'season_end', 'weekdays', 'period_start', 'period_end')
    actions = ['generate_daily_schedule']  # Добавляем кастомное действие

    def generate_daily_schedule(self, request, queryset):
        """
        Действие для формирования суточного плана.
        """
        if 'apply' in request.POST:
            # Получаем дату из формы
            form = SelectDateForm(request.POST)
            if form.is_valid():
                selected_date = form.cleaned_data['selected_date']
                selected_day = selected_date.weekday() + 1  # День недели: 1 = Понедельник, ..., 7 = Воскресенье

                # Фильтруем шаблоны
                templates = queryset.filter(
                    season_start__lte=selected_date,
                    season_end__gte=selected_date,
                    weekdays__contains=str(selected_day)
                )

                # Создаём рейсы в InfTablo
                created_count = 0
                for template in templates:
                    if not InfTablo.objects.filter(
                        flight=template.flight,
                        date1=selected_date
                    ).exists():
                        InfTablo.objects.create(
                            direction=template.flight.direction,
                            airline=template.flight.airline,
                            flight=template.flight.flight,
                            destination=template.flight.destination,
                            date1=selected_date,
                            time1=template.flight.time1,
                            status=None
                        )
                        created_count += 1

                self.message_user(request, f"Сформировано {created_count} рейсов на {selected_date}.")
                return

        # Если GET-запрос или форма неверна, показываем форму выбора даты
        form = SelectDateForm()
        return render(request, 'admin/select_date_form.html', {'form': form, 'queryset': queryset})

    generate_daily_schedule.short_description = "Сформировать суточный план"  # Подпись в админке

@staff_member_required
def generate_daily_schedule_view(request):
    """
    Формирование суточного плана на основе FlightTemplate и выбранной даты.
    """
    if request.method == "GET" and 'selected_date' in request.GET:
        # Получаем выбранную дату
        selected_date_str = request.GET.get('selected_date')
        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            return render(request, "admin/custom_generate_daily_schedule.html", {
                "messages": [{"message": "Неверный формат даты.", "level_tag": "error"}]
            })

        # Определяем день недели для выбранной даты
        selected_day = selected_date.weekday() + 1  # Преобразуем: 1 = Понедельник, ..., 7 = Воскресенье

        # Фильтруем шаблоны рейсов по сезону и дням вылета
        templates = FlightTemplate.objects.filter(
            season_start__lte=selected_date,  # Выбранная дата входит в сезон
            season_end__gte=selected_date,
            weekdays__contains=str(selected_day)  # День недели соответствует
        )

        created_count = 0  # Счётчик созданных записей
        for template in templates:
            # Проверяем, существует ли запись для этого рейса на указанную дату
            flight_instance = FlightNumber.objects.filter(flights=template.flight.flight).first()

            if not flight_instance:
                raise ValueError(f"Рейс {template.flight.flights} не найден в базе данных!")

            if not InfTablo.objects.filter(
                flight=flight_instance,
                date1=selected_date
            ).exists():
                InfTablo.objects.create(
                    # direction=template.flight.direction,
                    airline=template.flight.airline,
                    flight=flight_instance,  # Передаём объект FlightNumber
                    destination=template.flight.destination,
                    date1=selected_date,
                    time1=template.flight.time1,
                    status=None
                )

                created_count += 1

        # Уведомляем пользователя об успехе
        return render(request, "admin/custom_generate_daily_schedule.html", {
            "messages": [{"message": f"Сформировано {created_count} рейсов на {selected_date}.", "level_tag": "success"}]
        })

    # Если GET-запрос без выбранной даты
    return render(request, "admin/custom_generate_daily_schedule.html")





# Регистрируем модель и её админ-класс
admin.site.register(FlightTemplate, FlightTemplateAdmin)

admin.site.register(FlightNumber)
admin.site.register(Cities)
admin.site.register(Stoiki)
admin.site.register(Airline)
admin.site.register(Status)
admin.site.register(FlightForTemplate)

admin.site.register(InfTablo, InfTabloAdmin)
