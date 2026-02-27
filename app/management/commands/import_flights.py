import json
import os
from django.core.management.base import BaseCommand
from app.models import FlightsList
from django.conf import settings

class Command(BaseCommand):
    help = 'Import flights from JSON reference file'

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, 'app', 'fids_flights_reference.json')
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        count = 0
        created_count = 0
        updated_count = 0
        
        for item in data:
            flight_num = item.get('flightNum')
            direction = item.get('direction')
            airline = item.get('airline')
            aircraft = item.get('aircraft')
            
            origin_raw = item.get('origin', '')
            destination_raw = item.get('destination', '')

            origin_parts = origin_raw.split(' ', 1)
            origin_icao = origin_parts[0] if len(origin_parts) > 0 else ''
            origin_city = origin_parts[1] if len(origin_parts) > 1 else ''

            destination_parts = destination_raw.split(' ', 1)
            destination_icao = destination_parts[0] if len(destination_parts) > 0 else ''
            destination_city = destination_parts[1] if len(destination_parts) > 1 else ''

            obj, created = FlightsList.objects.update_or_create(
                flight_number=flight_num,
                defaults={
                    'direction': direction,
                    'airline': airline,
                    'aircraft': aircraft,
                    'origin_icao': origin_icao,
                    'origin_city': origin_city,
                    'destination_icao': destination_icao,
                    'destination_city': destination_city,
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
            count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} flights (Created: {created_count}, Updated: {updated_count})'))
