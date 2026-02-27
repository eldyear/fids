import os
import datetime
from django.db import models
from django.utils.text import get_valid_filename
from django.utils import timezone
import logging
from django.core.exceptions import ValidationError
from oss.storage_backends import GoAppStorage

logger = logging.getLogger(__name__)

def go_app_file_upload_path(instance, filename):
    # Динамическое определение пути для загрузки файла
    # Здесь вы можете добавить логику для создания поддиректорий,
    # например, на основе имени файла, даты и т.д.
    # Например: return os.path.join('some_subdirectory', filename)
    return filename # По умолчанию, сохраняем прямо в GO_APP_UPLOAD_DIR


class GoAppFile(models.Model):
    name = models.CharField(max_length=255, verbose_name="Имя файла (для идентификации)", blank=True, null=True)
    file = models.FileField(
        upload_to=go_app_file_upload_path,
        storage=GoAppStorage(), # Используем наше кастомное хранилище
        verbose_name="Файл для Go приложения"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    def __str__(self):
        return self.name if self.name else self.file.name

    def save(self, *args, **kwargs):
        # Если поле 'name' заполнено и это новый файл или файл был изменен
        if self.name and self.file:
            # Получаем расширение файла из оригинального имени, если оно есть
            # или если поле 'file' уже содержит имя (например, при редактировании)
            original_filename = self.file.name if self.file else ""
            _, ext = os.path.splitext(original_filename)

            # Если расширение не .svg или его нет, и поле 'name' содержит 'svg',
            # то предположим, что это .svg
            if not ext and '.svg' in self.name.lower():
                ext = '.svg'
            elif not ext:
                # Если расширения нет, и в name нет 'svg', можно установить по умолчанию или выбросить ошибку
                # Для примера установим .svg
                ext = '.svg'


            # Формируем новое имя файла
            # Предполагаем, что self.name содержит нужную часть, например "SU"
            # Если self.name = "SU", то новое имя будет "sky_priority_SU.svg"
            # Если self.name = "KGZ", то новое имя будет "sky_priority_KGZ.svg"
            new_file_name = f"sky_priority_{self.name}{ext}"

            # Удаляем недопустимые символы из имени файла
            new_file_name = get_valid_filename(new_file_name)

            # Если это новый файл (еще не сохранен) или имя файла изменилось
            # Проверяем, был ли файл фактически загружен (file.file - это ContentFile или аналогичный объект)
            # if self._state.adding or (self.pk and self.file.name != new_file_name):
            # Передаем новое имя файла в ContentFile, чтобы Django сохранил его под этим именем
            # Важно: нужно проверить, является ли self.file объектом File и не None
            if self.file:
                # Получаем текущий файл, чтобы его содержимое не потерялось
                current_file_content = self.file.read()
                from django.core.files.base import ContentFile
                self.file = ContentFile(current_file_content, name=new_file_name)
                # После создания ContentFile, если это был существующий файл,
                # его старый путь нужно будет удалить вручную или через сигнал,
                # так как Django не делает это автоматически при изменении имени.
                # Для нового файла это не проблема.

        super().save(*args, **kwargs) # Сохраняем объект GoAppFile

    def delete(self, *args, **kwargs):
        # Удаляем файл с диска при удалении объекта модели
        self.file.delete(save=False)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Файл для Go приложения"
        verbose_name_plural = "Файлы для Go приложения"

STATUS_CHOICES = (
    ('Регистрация','Регистрация'),('Посадка','Посадка'),('Отправлен','Отправлен'),(' ', ' '),
    ('По готовности','По готовности'),('Задержан','Задержан'),('Отменен','Отменен'), ('По расписанию','По расписанию'), ('Выполнен','Выполнен')
)

DIRECTION = (
    ('dep', 'Вылет'),
    ('arr', 'Прилет')
)

class Status(models.Model):
    status_id = models.CharField(max_length=2, verbose_name="ID статуса", blank=True, null=True)
    name_ru = models.CharField(max_length=50, verbose_name="Статус на русском", blank=True, null=True)
    name_ky = models.CharField(max_length=50, verbose_name="Статус на кыргызском", blank=True, null=True)
    name_en = models.CharField(max_length=50, verbose_name="Статус на английском", blank=True, null=True)

    def __str__(self):
        return "{}".format(self.name_ru)

    class Meta:
        db_table = 'Status'
        verbose_name = "Статус"
        verbose_name_plural = "Статусы"


class FlightNumber(models.Model):
    # flight_code = models.CharField(max_length=3,verbose_name="Код авиакомпании ", unique=True)
    flights = models.CharField(max_length=20,verbose_name="№ Рейса ")
    def __str__(self):
        return "{}".format(self.flights)

    class Meta:
        db_table = 'FlightNumber'
        verbose_name = "№ Рейса"
        verbose_name_plural = "№ Рейсов"

class Cities(models.Model):
    city_name_ru = models.CharField(max_length=50, verbose_name="Город на русском")
    city_name_ky = models.CharField(max_length=50, verbose_name="Город на кыргызском")
    city_name_en = models.CharField(max_length=50, verbose_name="Город на английском")
    iata_code = models.CharField(max_length=3, verbose_name="IATA код")
    icao_code = models.CharField(max_length=4, verbose_name="ICAO код", blank=True)
    def __str__(self):
        return "{}".format(self.city_name_ru)

    class Meta:
        db_table = 'City'
        verbose_name = "Город"
        verbose_name_plural = "Города"


class Stoiki(models.Model):
    stoiki = models.CharField(max_length=10, unique=True)  # Номер стойки
    sky_priority = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.stoiki} {'(Sky Priority)' if self.sky_priority else ''}"
    def get_number(self):
        return self.stoiki

    class Meta:
        db_table = 'Stoiki'
        verbose_name = "№ Стойки"
        verbose_name_plural = "№ Стоек"

class Gates(models.Model):
    gate = models.CharField(max_length=2,verbose_name="Gate № ")
    def __str__(self):
        return "Gate - {}".format(self.gate)
    def get_number(self):
        return self.gate

    class Meta:
        db_table = 'Gates'
        verbose_name = "Gate:"
        verbose_name_plural = "Gates:"

class Airline(models.Model):
    name = models.CharField(max_length=20, verbose_name="Авиакомпания", blank=True)
    code = models.CharField(max_length=3, verbose_name="Код авиакомпании", blank=True)
    logo = models.ImageField(upload_to='airline_logos/', verbose_name="Логотип", blank=True)
    svg_logo = models.FileField(upload_to='airline_logos/svg/', verbose_name="SVG логотип", blank=True)

    def save(self, *args, **kwargs):
        if Airline.objects.filter(code=self.code).exclude(pk=self.pk).exists():
            raise ValidationError(f"Авиакомпания с кодом '{self.code}' уже существует.")
        if self.svg_logo:
            # Получаем расширение файла
            svg_ext = self.svg_logo.name.split('.')[-1]
            # Создаем новое имя файла, используя поле code
            svg_new_filename = f"{self.code}.{svg_ext}"
            # Удаляем недопустимые символы из имени файла
            svg_new_filename = get_valid_filename(svg_new_filename)
            # Устанавливаем новое имя файла
            self.svg_logo.name = svg_new_filename

        super(Airline, self).save(*args, **kwargs)

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'Airline'
        verbose_name = "Авиакомпания"
        verbose_name_plural = "Авиакомпании"

from django.utils import timezone

class InfTablo(models.Model):
    direction = models.CharField(max_length=3, choices=DIRECTION)
    airline = models.CharField(max_length=50, verbose_name="Код авиакомпании", blank=True, null=True)
    flight = models.ForeignKey(
        FlightNumber,
        on_delete=models.CASCADE,
        verbose_name="Рейс № *",
    )
    destination = models.ForeignKey(
        Cities,
        on_delete=models.CASCADE,
        verbose_name="Пункт назначение *",
    )
    date1 = models.DateField("Дата плановая*", null=True)
    time1 = models.TimeField("Время плановая*", null=True)
    arr_time = models.TimeField("Время прибытия", blank=True, null=True)
    last_date = models.DateField("Дата (факт)", blank=True, null=True)
    last_time = models.TimeField("Время (факт)", blank=True, null=True)
    status = models.ForeignKey(
        Status,
        on_delete=models.CASCADE,
        verbose_name="Статус",
        blank=True,
        null=True
    )
    stoika = models.ManyToManyField(
        Stoiki,
        related_name='CheckDesk',
        verbose_name="Табло №",
        blank=True
    )

    gate = models.ManyToManyField(
        Gates,
        related_name='Gate',
        verbose_name="Gate:",
        blank=True
    )

    # Field for API synchronization
    current_flight_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID из API")

    # Dynamic Sky Priority Desks for the flight
    sky_priority_desks = models.ManyToManyField(
        Stoiki,
        related_name='sky_priority_flights',
        verbose_name="Sky Priority Desks",
        blank=True
    )


    def __str__(self):
        return "{}".format(self.destination)


    class Meta:
        db_table = "InfTablo"
        verbose_name = '"Суточный план"'
        verbose_name_plural = "Суточный план"

class FlightForTemplate(models.Model):
    airline = models.ForeignKey(
        Airline,
        on_delete=models.CASCADE,
        verbose_name="Авиакомпания *",
        related_name='template_airline',
        default=1
    )
    flight = models.ForeignKey(
        FlightNumber,
        on_delete=models.CASCADE,
        verbose_name="Рейс № *",
        related_name='template_flight',
        default=1
    )
    destination = models.ForeignKey(
        Cities,
        on_delete=models.CASCADE,
        verbose_name="Пункт назначение *",
        related_name='template_destination',
        default=1
    )



    def __str__(self):
        return "{}".format(self.flight)

    class Meta:
        verbose_name = "Информация о рейсе"
        verbose_name_plural = "Информации о рейсах"

class FlightTemplate(models.Model):
    """
    Модель для хранения шаблонов рейсов.
    """
    direction = models.CharField("Направление *", max_length=10, default="", choices=DIRECTION)
    season_start = models.DateField("Начало сезона")
    season_end = models.DateField("Конец сезона")
    weekdays = models.CharField(
        "Дни вылета",
        max_length=20,
        help_text="Введите дни недели через запятую, например: 1,3,5 для понедельника, среды и пятницы"
    )
    period_start = models.DateField("Начало периода рейса")
    period_end = models.DateField("Конец периода рейса")
    time = models.TimeField("Время плановая*", null=True)

    flight = models.ForeignKey(
        FlightForTemplate,  # Связываем с моделью InfTablo
        on_delete=models.CASCADE,  # Удаление рейса приведёт к удалению всех шаблонов
        verbose_name="Рейс",
        related_name="flight_templates"  # Обратная связь: InfTablo.flight_templates.all()
    )


    def __str__(self):
        return f"Шаблон рейса {self.flight.flight} ({self.season_start} - {self.season_end})"

    class Meta:
        verbose_name = "Шаблон рейса"
        verbose_name_plural = "Шаблоны рейсов"

class UpdateLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.timestamp)

class FlightsList(models.Model):
    flight_number = models.CharField(max_length=10, verbose_name="Номер рейса")
    direction = models.CharField(max_length=10, verbose_name="Направление")
    airline = models.CharField(max_length=3, verbose_name="Авиакомпания", blank=True, null=True)
    origin_icao = models.CharField(max_length=5, verbose_name="ICAO вылета", blank=True, null=True)
    origin_city = models.CharField(max_length=100, verbose_name="Город вылета", blank=True, null=True)
    destination_icao = models.CharField(max_length=5, verbose_name="ICAO назначения", blank=True, null=True)
    destination_city = models.CharField(max_length=100, verbose_name="Город назначения", blank=True, null=True)
    aircraft = models.CharField(max_length=20, verbose_name="Тип ВС", blank=True, null=True)

    def __str__(self):
        return self.flight_number

    class Meta:
        verbose_name = "Справочник рейсов"
        verbose_name_plural = "Справочник рейсов"
