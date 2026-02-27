from django.db import models
from django.utils import timezone

class Flight(models.Model):
    """
    Модель для хранения скопированных данных о рейсе.
    """
    # Уникальный идентификатор рейса, скопированный из FIDS
    flight_id = models.CharField(max_length=10, unique=True, verbose_name="ID Рейса из FIDS")
    
    # Скопированные данные о рейсе
    direction = models.CharField(max_length=3, verbose_name="Направление")
    airline = models.CharField(max_length=50, verbose_name="Авиакомпания")
    flight_num = models.CharField(max_length=20, verbose_name="Номер рейса")
    destination = models.CharField(max_length=50, verbose_name="Пункт назначения")
    date_planned = models.DateField("Дата вылета", null=True, blank=True)
    time_planned = models.TimeField("Время вылета", null=True, blank=True)
    total_weight = models.DecimalField(
        "Общий вес багажа (кг)", 
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    def __str__(self):
        return f"Рейс: {self.flight_num} ({self.destination})"
    
    class Meta:
        verbose_name = "Рейс"
        verbose_name_plural = "Рейсы"


class Container(models.Model):
    """
    Модель для хранения данных о контейнере.
    """
    # Уникальный ID контейнера, сканируемый со штрихкода.
    # !!! УДАЛЕНО: unique=True !!!
    barcode = models.CharField(max_length=50, verbose_name="Штрихкод контейнера") 
    
    # Связь с моделью Flight
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, verbose_name="Рейс")
    
    # Количество багажа в контейнере
    baggage_count = models.IntegerField(default=0, verbose_name="Количество багажа")

    # Статус контейнера (открыт/закрыт)
    is_closed = models.BooleanField(default=False, verbose_name="Закрыт")
    
    # Дополнительная информация
    last_scanned_at = models.DateTimeField(auto_now=True, verbose_name="Последнее сканирование")
    
    def __str__(self):
        return f"Контейнер: {self.barcode} ({self.flight.flight_num})"
        
    class Meta:
        verbose_name = "Контейнер"
        verbose_name_plural = "Контейнеры"
        # !!! ДОБАВЛЕНО: Уникальным является сочетание штрихкода И рейса !!!
        unique_together = ('barcode', 'flight')


class Baggage(models.Model):
    """
    Модель для хранения данных о каждой единице багажа.
    """
    # !!! УДАЛЕНО: unique=True !!!
    barcode = models.CharField(max_length=50, verbose_name="Штрихкод багажа")

    # Связь с моделью Container
    container = models.ForeignKey(Container, on_delete=models.CASCADE, verbose_name="Контейнер")

    # Данные, извлеченные из штрихкода (для поиска)
    baggage_num = models.CharField(max_length=10, verbose_name="Номер багажа")
    airline_code = models.CharField(max_length=3, verbose_name="Код авиакомпании")
    destination_code = models.CharField(max_length=3, verbose_name="Код назначения")
    
    # Время сканирования
    scanned_at = models.DateTimeField(auto_now_add=True, verbose_name="Время сканирования")
    
    def __str__(self):
        return f"Багаж: {self.barcode} ({self.container.barcode})"
        
    class Meta:
        verbose_name = "Багаж"
        verbose_name_plural = "Багаж"
        # ДОБАВЛЕНИЕ ИНДЕКСА ДЛЯ СКОРОСТИ (рекомендовано)
        indexes = [
            models.Index(fields=['barcode', 'scanned_at']),
        ]