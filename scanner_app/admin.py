from django.contrib import admin
from .models import BarcodeScan

@admin.register(BarcodeScan)
class BarcodeScanAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'timestamp', 'user', 'passenger_name', 'carrier_code', 
        'flight_number_str', 'pnr', 'seat_number', 'is_duplicate'
    ]
    list_filter = [
        'timestamp', 'carrier_code', 'is_duplicate', 'flight__destination', 'user'
    ]
    search_fields = [
        'passenger_name', 'pnr', 'raw_barcode', 'carrier_code', 
        'flight_number_str', 'flight__flight__flights', 'user__username'
    ]
    readonly_fields = ['timestamp']
    fieldsets = (
        ('Основная информация', {
            'fields': ('timestamp', 'user', 'raw_barcode', 'is_duplicate')
        }),
        ('Пассажир', {
            'fields': ('passenger_name', 'pax_type', 'pnr', 'seat_number')
        }),
        ('Рейс', {
            'fields': ('carrier_code', 'flight_number_str', 'flight', 'flight_date_info')
        }),
        ('Аэропорты', {
            'fields': ('origin_airport', 'destination_airport')
        }),
        ('Дополнительная информация', {
            'fields': ('scanner_prefix', 'sequence_number', 'additional_info_tail', 'compartment_code')
        }),
        ('Оригинальные данные сканера', {
            'fields': ('parsed_data_json',),
            'classes': ('collapse',),  # Свернуто по умолчанию
        }),
    )
    list_per_page = 50
    date_hierarchy = 'timestamp'


