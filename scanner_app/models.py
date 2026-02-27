# scanner_app/models.py
from django.db import models
from django.contrib.auth.models import User
from app.models import InfTablo # Импортируем модель Flight

class BarcodeScan(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        null=True,
        blank=True
    )
    raw_barcode = models.TextField()
    scanner_prefix = models.CharField(max_length=50, blank=True, null=True)
    pax_type = models.CharField(max_length=50, blank=True, null=True)
    passenger_name = models.CharField(max_length=255, blank=True, null=True)
    pnr = models.CharField(max_length=20, blank=True, null=True)
    origin_airport = models.CharField(max_length=3, blank=True, null=True)
    destination_airport = models.CharField(max_length=3, blank=True, null=True)
    carrier_code = models.CharField(max_length=50, blank=True, null=True) # Код перевозчика из сканера
    flight_number_str = models.CharField(max_length=50, blank=True, null=True) # Номер рейса из сканера
    
    # Ссылка на объект Flight из FIDS
    flight = models.ForeignKey(
        InfTablo,
        on_delete=models.SET_NULL, # Если рейс удаляется из FIDS, ссылка здесь обнуляется
        null=True,
        blank=True,
        related_name='scans'
    )

    flight_date_info = models.CharField(max_length=50, blank=True, null=True)
    flight_date = models.DateField(blank=True, null=True, verbose_name="Дата вылета (YYYY-MM-DD)")
    seat_number = models.CharField(max_length=50, blank=True, null=True)
    sequence_number = models.CharField(max_length=50, blank=True, null=True)
    additional_info_tail = models.CharField(max_length=255, blank=True, null=True)
    compartment_code = models.CharField(max_length=50, blank=True, null=True)
    is_duplicate = models.BooleanField(default=False)
    
    # Suspicious flag (e.g. scanned after flight departure)
    is_suspicious = models.BooleanField(default=False, verbose_name="Подозрительный")
    suspicious_reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Причина подозрительности")
    
    # Полные оригинальные данные от сканера в JSON формате
    parsed_data_json = models.JSONField(blank=True, null=True, verbose_name="Оригинальные данные сканера")

    def __str__(self):
        return f"Scan {self.id} for {self.passenger_name} on {self.flight_number_str} ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"