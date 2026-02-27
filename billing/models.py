# flights/models.py
from django.db import models, transaction
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from datetime import datetime, timedelta


class Airport(models.Model):
    code = models.CharField(max_length=4, unique=True, verbose_name="Код аэропорта")
    name = models.CharField(max_length=100, verbose_name="Название аэропорта")

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = "Аэропорт"
        verbose_name_plural = "Аэропорты"

class Airline(models.Model):
    code = models.CharField(max_length=4, unique=True, verbose_name="Код авиакомпании")
    name = models.CharField(max_length=100, verbose_name="Название авиакомпании")

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = "Авиакомпания"
        verbose_name_plural = "Авиакомпании"

class Flight(models.Model):
    DIRECTION_CHOICES = [
        ('O', 'Вылет'),
        ('P', 'Прилет'),
    ]

    REGION_CHOICES = [
        ('1', 'СНГ'),
        ('2', 'Внутренние'),
        ('3', 'Чартерные'),
        ('4', 'Международные'),

    ]
    is_active = models.BooleanField(default=True)
    date = models.DateField(verbose_name="Дата рейса")
    region = models.CharField(max_length=50, choices=REGION_CHOICES, verbose_name="Регион")
    direction = models.CharField(max_length=1, choices=DIRECTION_CHOICES, verbose_name="Направление")
    flight_num = models.CharField(max_length=20, verbose_name="Номер рейса")

    date_plan = models.CharField(max_length=100, blank=True, null=True, verbose_name="Дата по плану (API)")
    date_fact = models.CharField(max_length=100, blank=True, null=True, verbose_name="Фактическая дата (API)")
    airline = models.ForeignKey(Airline, on_delete=models.SET_NULL, null=True, related_name='departing_flights', verbose_name="Авиакомпания")
    aircraft_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="Тип ВС")
    board_num = models.CharField(max_length=50, blank=True, null=True, verbose_name="Бортовой номер")
    
    dep_airport = models.ForeignKey(Airport, on_delete=models.SET_NULL, null=True, related_name='departing_flights', verbose_name="Аэропорт вылета")
    arr_airport = models.ForeignKey(Airport, on_delete=models.SET_NULL, null=True, related_name='arriving_flights', verbose_name="Аэропорт прилета")
    
    time = models.CharField(max_length=10, blank=True, null=True, verbose_name="Время")
    estimated_time = models.CharField(max_length=10, blank=True, null=True, verbose_name="Время ожидаемое")
    actual_time = models.CharField(max_length=10, blank=True, null=True, verbose_name="Время фактическое")
    codeshare = models.CharField(max_length=100, blank=True, null=True, verbose_name="Код-шер")
    stand = models.CharField(max_length=50, blank=True, null=True, verbose_name="Стойка")
    board_base = models.CharField(max_length=50, blank=True, null=True, verbose_name="Тип рейса")
    checkin = models.CharField(max_length=50, blank=True, null=True, verbose_name="Регистрация")
    gate = models.CharField(max_length=50, blank=True, null=True, verbose_name="Выход на посадку")
    tech_card = models.TextField(blank=True, null=True, verbose_name="Техническая карта (из API)")
    current_flight_id = models.TextField(blank=True, null=True, verbose_name="ID текущего рейса (из API)")
    paired_flight_id = models.TextField(blank=True, null=True, verbose_name="ID связанного рейса (из API)")
    

    # max_takeoff_weight = models.CharField(
    #     max_length=50,
    #     blank=True,
    #     null=True,
    #     verbose_name="Максимальная взлетная масса"
    # )

    

    linked_flight = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Связанный рейс (прилет/вылет)"
    )

    class Meta:
        # unique_together = ('date', 'region', 'direction', 'flight_num')
        verbose_name = "Рейс"
        verbose_name_plural = "Рейсы"
        ordering = ['date', 'time']

    def __str__(self):
        return f"Рейс {self.flight_num} {self.get_direction_display()} {self.date.strftime('%d.%m.%Y')}"
    
class Firm(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название фирмы")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Фирма"
        verbose_name_plural = "Фирмы"

from django.db.models import Max
    
class TechCard(models.Model):
    tech_card_num = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
        verbose_name="Номер техкарты"
    )
    def save(self, *args, **kwargs):
        # Присваиваем номер только при создании объекта
        if not self.id:  # Проверяем, является ли объект новым
            # Блокируем таблицу для предотвращения гонки данных
            with transaction.atomic():
                max_num = TechCard.objects.select_for_update().aggregate(Max('tech_card_num'))['tech_card_num__max']
                
                # Если максимальный номер найден, увеличиваем его на 1
                if max_num:
                    self.tech_card_num = max_num + 1
                else:
                    # Если техкарт еще нет, начинаем с 1001
                    self.tech_card_num = 1001
        
        super().save(*args, **kwargs)

    flight = models.ForeignKey(
        Flight,
        on_delete=models.CASCADE,
        related_name='tech_cards',
        verbose_name="Связанный рейс"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tech_cards',
        verbose_name="Автор техкарты"
    )
    # НОВЫЕ ПОЛЯ: Информация о заправке
    fueler = models.ForeignKey(
        Firm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_techcards',
        verbose_name="ТЗК"
    )
    fuel_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Количество топлива"
    )
    fuel_unit = models.CharField(
        max_length=10,
        choices=[('kg', 'кг'), ('ton', 'тонна')],
        default='kg',
        verbose_name="Единица измерения топлива"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    tech_card_text = models.TextField(blank=True, null=True, verbose_name="Сгенерированный текст техкарты")
    max_takeoff_weight = models.CharField(max_length=50, blank=True, null=True, verbose_name="Максимальная взлетная масса")
    is_closed = models.BooleanField(default=False, verbose_name="Закрыта")
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_techcards', verbose_name="Кем закрыта")
    
    def __str__(self):
        return f"Техкарта для рейса {self.flight.flight_num} от {self.flight.date}"

    class Meta:
        verbose_name = "Техкарта"
        verbose_name_plural = "Техкарты"
        unique_together = ('flight', 'author')

# --- НОВАЯ МОДЕЛЬ ДЛЯ ТИПОВ УСЛУГ ---
class ServiceType(models.Model):
    CATEGORY_CHOICES = [
    ('int', 'числовое'),
    ('pass', 'пассажиры'),
    ('time', 'временное'),
    ]
    code = models.IntegerField(unique=True, verbose_name="Код типа услуги")
    name = models.CharField(max_length=100, verbose_name="Название типа услуги")
    category = models.CharField(
        choices=CATEGORY_CHOICES,
        max_length=50,
        verbose_name="Категория услуги",
        help_text="Используется для группировки полей в форме (e.g., 'passenger', 'duration')",
        null=True
    )

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        verbose_name = "Тип услуги"
        verbose_name_plural = "Типы услуг"
        ordering = ['name']


class Service(models.Model):
    # Поля, которые всегда необходимы
    tech_card = models.ForeignKey('TechCard', on_delete=models.CASCADE, related_name='services')
    service_type = models.ForeignKey('ServiceType', on_delete=models.CASCADE)
    description = models.TextField(verbose_name="Примечание", blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='services')
    
    # Поля для услуг с категорией 'pass' (пассажиры)
    adults_count = models.PositiveIntegerField(
        verbose_name="Количество взрослых",
        default=0,
        null=True,
        blank=True
    )
    children_count = models.PositiveIntegerField(
        verbose_name="Количество детей",
        default=0,
        null=True,
        blank=True
    )
    infants_count = models.PositiveIntegerField(
        verbose_name="Количество младенцев",
        default=0,
        null=True,
        blank=True
    )

    # Поля для услуг с категорией 'time' (время)
    start_time = models.TimeField(null=True, blank=True, verbose_name="Время начала")
    end_time = models.TimeField(null=True, blank=True, verbose_name="Время окончания")
    # Используем `duration_field` для прямого ввода продолжительности
    duration_field = models.DurationField(
        verbose_name="Продолжительность (чч:мм)",
        null=True,
        blank=True
    )
    
    # Поля для услуг с категорией 'int' (числовое)
    quantity = models.PositiveIntegerField(
        verbose_name="Количество",
        null=True,
        blank=True
    )
    unit_of_measure = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Единица измерения"
    )

    # Метод-свойство для расчета длительности на основе start_time и end_time
    @property
    def calculated_duration(self):
        if self.start_time and self.end_time:
            dummy_date = datetime(2023, 1, 1)
            start_dt = datetime.combine(dummy_date, self.start_time)
            end_dt = datetime.combine(dummy_date, self.end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            return end_dt - start_dt
        return None
    
    @property
    def display_duration(self):
        """Возвращает введенную длительность, если она есть, иначе вычисленную."""
        if self.duration_field:
            return self.duration_field
        return self.calculated_duration

    @property
    def passengers_display(self):
        return f"{self.adults_count or 0}/{self.children_count or 0}/{self.infants_count or 0}"

    def __str__(self):
        return f"{self.service_type.name} для техкарты №{self.tech_card.id}"
        
    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ['-id']

class ServicePrice(models.Model):
    service_type = models.OneToOneField(ServiceType, on_delete=models.CASCADE, verbose_name="Тип услуги", related_name="price")
    price_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена за единицу"
    )

    def __str__(self):
        return f"{self.service_type.name}: {self.price_per_unit}"
    
    class Meta:
        verbose_name = "Цена услуги"
        verbose_name_plural = "Цены услуг"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    signature = models.ImageField(upload_to='signatures/', blank=True, null=True)

    def __str__(self):
        return self.user.username
    

class LogEntry(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Создано'),
        ('UPDATED', 'Обновлено'),
        ('DELETED', 'Удалено'),
    ]

    # Добавляем related_name, чтобы избежать конфликта с admin.LogEntry
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Пользователь", related_name='flights_logentry_set')
    action_time = models.DateTimeField(auto_now_add=True, verbose_name="Время действия")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="Действие")
    
    # Добавляем related_name здесь
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="Тип объекта", related_name='flights_logentry_set')
    object_id = models.PositiveIntegerField(verbose_name="ID объекта")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    changes = models.JSONField(verbose_name="Изменения")

    class Meta:
        verbose_name = "Журнал действий"
        verbose_name_plural = "Журнал действий"
        ordering = ['-action_time']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.content_object}"