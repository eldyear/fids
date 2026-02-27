# flights/forms.py
from django import forms
from datetime import datetime, date
from .models import Flight, Service, ServiceType, TechCard # Добавляем ServiceType
from django.contrib.auth.models import User
from django.forms import TimeInput

class FlightFilterForm(forms.Form):
    date = forms.DateField(
        label="Дата",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=date.today(),
        input_formats=['%Y-%m-%d', '%d.%m.%y', '%d.%m.%Y']
    )

    direction = forms.ChoiceField(
        label="Направление",
        choices=[('', 'Все')] + list(Flight.DIRECTION_CHOICES),
        required=False
    )
    
    region = forms.ChoiceField(
        label="Регион",
        choices=[('', 'Все')],
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regions = Flight.objects.values_list('region', flat=True).distinct().order_by('region')
        region_choices = [('', 'Все')] + [(r, r) for r in regions]
        self.fields['region'].choices = region_choices

class TimeInput24H(TimeInput):
    def __init__(self, *args, **kwargs):
        kwargs['format'] = '%H:%M'
        super().__init__(*args, **kwargs)

# --- ОБНОВЛЕННАЯ ФОРМА ДЛЯ УСЛУГ ---
class ServiceForm(forms.ModelForm):
    # Явно добавляем скрытое поле для tech_card
    tech_card = forms.ModelChoiceField(
        queryset=TechCard.objects.all(),
        widget=forms.HiddenInput(),
        required=False # Оно не обязательно, так как мы заполним его в view
    )

    class Meta:
        model = Service
        # Убедитесь, что все поля из модели здесь указаны!
        fields = [
            'tech_card', # <-- Добавлено поле
            'service_type',
            'description',
            'quantity',
            'unit_of_measure',
            'adults_count',
            'children_count',
            'infants_count',
            'duration_field', # <--- Проверьте, что это поле есть в вашей модели!
            'start_time',
            'end_time',
        ]
        widgets = {
            'start_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 1}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_type'].queryset = ServiceType.objects.all().order_by('code')
        self.fields['service_type'].label_from_instance = lambda obj: f"{obj.code} {obj.name}"

class LogFilterForm(forms.Form):
    start_date = forms.DateField(label='С', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='По', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    user = forms.ModelChoiceField(queryset=User.objects.all(), label='Пользователь', required=False)

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='Выберите файл Excel (.xlsx)',
        help_text='Загрузите файл для обновления типов услуг.'
    )