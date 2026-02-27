# flights/admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Airport, Flight, Service, ServiceType, Airline, UserProfile, TechCard, Firm # Добавляем ServiceType
from django.utils.html import format_html

import pandas as pd
from django.urls import path, reverse
from django.shortcuts import render, redirect

from .forms import ExcelUploadForm


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

    change_list_template = 'admin/flights/servicetype/changelist.html'

    def changelist_view(self, request, extra_context=None):
        # Получаем стандартный контекст админки через self.admin_site
        context = self.admin_site.each_context(request)
        
        # Добавляем ссылку на нашу страницу импорта в контекст
        context['import_url'] = reverse('admin:import_service_types')
        
        # Вызываем оригинальный метод, передавая ему обновленный контекст
        return super().changelist_view(request, extra_context=context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel), name='import_service_types'),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES['excel_file']

                if not excel_file.name.endswith('.xlsx'):
                    messages.error(request, 'Неверный формат файла. Пожалуйста, загрузите файл .xlsx')
                    return redirect('admin:import_service_types')
                
                try:
                    df = pd.read_excel(excel_file)
                    updated_count = 0
                    created_count = 0

                    # Убедитесь, что имена колонок соответствуют названиям в Excel
                    code_col = 'code'
                    name_col = 'name'
                    category_col = 'category'

                    for index, row in df.iterrows():
                        code = row.get(code_col)
                        name = row.get(name_col)
                        # --- ПОЛУЧАЕМ ЗНАЧЕНИЕ КАТЕГОРИИ ИЗ EXCEL ---
                        category = row.get(category_col)
                        
                        if not code or not name:
                            messages.warning(request, f'Строка {index + 1} пропущена. Отсутствует "{code_col}" или "{name_col}".')
                            continue

                        # --- ДОБАВЛЯЕМ category В МЕТОД update_or_create ---
                        obj, created = ServiceType.objects.update_or_create(
                            code=code,
                            defaults={'name': name, 'category': category}
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    messages.success(request, f'Импорт завершен: создано {created_count} новых записей, обновлено {updated_count} существующих.')
                
                except KeyError:
                    messages.error(request, f'Ошибка: В файле Excel отсутствуют необходимые колонки "{code_col}", "{name_col}" или "{category_col}".')
                except Exception as e:
                    messages.error(request, f'Произошла ошибка при обработке файла: {e}')
                
                return redirect('admin:import_service_types')
        else:
            form = ExcelUploadForm()

        context = self.admin_site.each_context(request)
        context.update({
            'form': form,
            'title': 'Импорт типов услуг из Excel',
            'has_permission': self.has_add_permission(request),
        })
        return render(request, 'admin/import_excel.html', context)

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        'flight_num', 
        'date', 
        'date_fact', 
        'direction', 
        
        'current_flight_id', 
        'is_active', 
    )
    # This is the key part to control the sorting order
    # '-' makes the sorting in descending order (newest first)
    ordering = ('-date',) 

    # If you also want to see the linked flights and filter them in the list view
    list_filter = ('is_active', 'board_base', 'date', 'direction')
    search_fields = ('flight_num', 'board_num', 'dep_airport__code', 'arr_airport__code')
    
    # This allows you to edit fields directly in the list view (optional)
    list_editable = ('is_active',)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.register(Airport)
admin.site.register(Firm)
admin.site.register(Airline)
# admin.site.register(Flight)
admin.site.register(Service)
# admin.site.register(ServiceType) # Регистрируем новую модель
admin.site.register(TechCard)