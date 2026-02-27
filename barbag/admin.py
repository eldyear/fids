from django.contrib import admin
from .models import Flight, Container, Baggage

@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ('flight_num', 'destination', 'date_planned', 'time_planned', 'flight_id')
    search_fields = ('flight_num', 'destination', 'flight_id')

@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'flight', 'baggage_count', 'is_closed', 'last_scanned_at')
    list_filter = ('is_closed', 'flight')
    search_fields = ('barcode',)
    readonly_fields = ('last_scanned_at',)

@admin.register(Baggage)
class BaggageAdmin(admin.ModelAdmin):
    list_display = ('barcode', 'container', 'baggage_num', 'airline_code', 'scanned_at')
    list_filter = ('container__is_closed', 'container__flight')
    search_fields = ('barcode', 'baggage_num')
    readonly_fields = ('scanned_at',)