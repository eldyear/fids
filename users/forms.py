# forms.py
from django import forms
from django.utils import timezone
from app.models import InfTablo, Status, Stoiki, FlightForTemplate, Airline, FlightNumber, Cities, Gates
from datetime import date
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename

class InfTabloForm(forms.ModelForm):
    stoika_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-style', 'placeholder': 'например 1,2,3'}),
        label="Стойки"
    )
    gate_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-style', 'placeholder': 'например 1,2,3'}),
        label="Гейты"
    )

    class Meta:
        model = InfTablo
        fields = [
            'direction', 'airline', 'flight', 'destination', 'date1',
            'time1', 'last_date', 'last_time', 'status'
        ]
        widgets = {
            'date1': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-style date1'},
                format='%Y-%m-%d',
            ),
            'last_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-style'},
                format='%Y-%m-%d'
            ),
            'time1': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-style'},
                format='%H:%M'
            ),
            'arr_time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-style'},
                format='%H:%M'
            ),
            'last_time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-style'},
                format='%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Заполнение поля ввода стойки, если объект уже существует
        if self.instance.pk:  # Если форма редактирует существующий объект
            self.fields['stoika_input'].initial = ",".join(
                str(stoika.stoiki) for stoika in self.instance.stoika.all()
            )
            self.fields['gate_input'].initial = ",".join(
                str(gate.gate) for gate in self.instance.gate.all()
            )

        self.fields['direction'].label = "Направление"
        self.fields['airline'].label = "А/К"
        self.fields['flight'].label = "Рейс №"
        self.fields['destination'].label = "Город"
        self.fields['date1'].label = "Дата"
        self.fields['time1'].label = "Время"
        self.fields['last_date'].label = "Дата факт."
        self.fields['last_time'].label = "Время факт."
        self.fields['status'].label = "Статус"
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-style')

    def clean_stoika_input(self):
        stoika_input = self.cleaned_data.get('stoika_input')
        if not stoika_input:
            return []

        stoika_ids = [s.strip() for s in stoika_input.split(",")]
        stoika_objects = []
        for stoika_id in stoika_ids:
            try:
                stoika_objects.append(Stoiki.objects.get(stoiki=stoika_id))
            except Stoiki.DoesNotExist:
                raise forms.ValidationError(f"Стойка с номером '{stoika_id}' не найдена.")

        return stoika_objects

    def clean_gate_input(self):
        gate_input = self.cleaned_data.get('gate_input')
        if not gate_input:
            return []

        gate_ids = [g.strip() for g in gate_input.split(",")]
        gate_objects = []
        for gate_id in gate_ids:
            try:
                gate_objects.append(Gates.objects.get(gate=gate_id))
            except Gates.DoesNotExist:
                raise forms.ValidationError(f"Гейт с номером '{gate_id}' не найден.")

        return gate_objects

    def save(self, commit=True):
        # Проверяем, редактируем ли мы существующий объект
        instance = super().save(commit=False)  # Получаем объект, но не сохраняем в базе
        stoika_objects = self.cleaned_data.get('stoika_input')  # ManyToMany поле
        gate_objects = self.cleaned_data.get('gate_input')  # ManyToMany поле

        if commit:
            instance.save()  # Сохраняем сам объект
            if stoika_objects is not None:
                instance.stoika.set(stoika_objects)  # Устанавливаем стойки (ManyToMany поле)
            if gate_objects is not None:
                instance.gate.set(gate_objects)  # Устанавливаем гейты (ManyToMany поле)
        return instance

    def clean_last_time(self):
        last_time = self.cleaned_data.get('last_time')
        if last_time and timezone.now().time() >= last_time:
            sent_status = Status.objects.filter(name_ru="Отправлен").first()
            if sent_status:
                self.instance.status = sent_status
        return last_time

    def clean(self):
        cleaned_data = super().clean()
        date1 = cleaned_data.get('date1')
        last_date = cleaned_data.get('last_date')

        if date1 and last_date and last_date < date1:
            self.add_error('last_date', 'Последняя дата не может быть раньше первой даты.')

        return cleaned_data


    

class DateFilterForm(forms.Form):
    selected_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                'type': 'date',
                'class': 'date-picker'
            }
        ),
        label=None,  # Remove the label tag
        initial=date.today
    )



class SelectDateForm(forms.Form):
    selected_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label=" ",
        initial=date.today  # Устанавливаем текущую дату по умолчанию
    )

from app.models import FlightTemplate


class FlightTemplateForm(forms.ModelForm):
    class Meta:
        model = FlightTemplate
        fields = [
            'direction', 'season_start', 'season_end', 'weekdays', 
            'period_start', 'period_end', 'time', 'flight'
        ]
        widgets = {
            'season_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-style date1'},format='%Y-%m-%d'),
            'season_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-style date1'},format='%Y-%m-%d'),
            'period_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-style date1'},format='%Y-%m-%d'),
            'period_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-style date1'},format='%Y-%m-%d'),
            'time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-style'},format='%H:%M'),
            'weekdays': forms.TextInput(attrs={'placeholder': 'Например: 1,3,5', 'class': 'form-style'}),
            'direction': forms.Select(attrs={'class': 'form-style'}),
            'flight': forms.Select(attrs={'class': 'form-style'}),
        }

from django.contrib.auth.forms import AuthenticationForm

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',  # Добавляем Bootstrap стиль
            'placeholder': 'Имя пользователя'
        }),
        label=''  # Отключаем метку
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',  # Добавляем Bootstrap стиль
            'placeholder': 'Пароль'
        }),
        label=''  # Отключаем метку
    )


from app.models import FlightForTemplate, Airline, FlightNumber, Cities
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename

class FlightForTemplateForm(forms.ModelForm):
    # Поля для ввода текста вместо выбора
    airline_name = forms.CharField(label="Авиакомпания *", max_length=255)
    airline_code = forms.CharField(label="Код авиакомпании *", max_length=3)
    svg_logo = forms.FileField(label="SVG логотип", required=False)  # Поле для загрузки SVG логотипа
    flight_number = forms.CharField(label="Рейс № *", max_length=255)
    
    # Поля для ввода названий города на трех языках
    destination_name_ru = forms.CharField(label="Город на русском *", max_length=50)
    destination_name_ky = forms.CharField(label="Город на кыргызском *", max_length=50)
    destination_name_en = forms.CharField(label="Город на английском *", max_length=50)
    
    # Поля для IATA и ICAO кодов
    iata_code = forms.CharField(label="IATA код *", max_length=3)
    icao_code = forms.CharField(label="ICAO код", max_length=4, required=False)

    class Meta:
        model = FlightForTemplate
        fields = []  # Исключаем стандартные поля

    # Валидация IATA кода
    def clean_iata_code(self):
        iata_code = self.cleaned_data['iata_code']
        if not iata_code.isalpha() or len(iata_code) != 3:
            raise forms.ValidationError("IATA код должен состоять из 3 букв.")
        return iata_code

    # Валидация кода авиакомпании
    def clean_airline_code(self):
        airline_code = self.cleaned_data['airline_code']
        if not airline_code.isalpha() or len(airline_code) < 2:
            raise forms.ValidationError("Код авиакомпании должен состоять из 3 букв.")
        return airline_code

    # Переопределение метода save
    def save(self, commit=True):
        # Создаем или находим существующую авиакомпанию
        airline, created = Airline.objects.get_or_create(
            name=self.cleaned_data['airline_name'],
            defaults={'code': self.cleaned_data['airline_code']}  # Добавляем код авиакомпании
        )

        # Если авиакомпания уже существует, обновляем её код и логотип
        if not created:
            airline.code = self.cleaned_data['airline_code']
        if self.cleaned_data.get('svg_logo'):
            svg_logo_file = self.cleaned_data['svg_logo']
            # Устанавливаем новое имя файла
            svg_ext = svg_logo_file.name.split('.')[-1]
            svg_new_filename = f"{airline.code}.{svg_ext}"
            svg_new_filename = get_valid_filename(svg_new_filename)
            svg_logo_file.name = svg_new_filename
            airline.svg_logo = svg_logo_file

            airline.save()  # Сохраняем изменения в авиакомпании

        # Создаем или находим существующий рейс
        flight, _ = FlightNumber.objects.get_or_create(flights=self.cleaned_data['flight_number'])
        
        # Создаем или находим существующий город с учетом всех полей
        destination, _ = Cities.objects.get_or_create(
            city_name_ru=self.cleaned_data['destination_name_ru'],
            defaults={
                'city_name_ky': self.cleaned_data['destination_name_ky'],
                'city_name_en': self.cleaned_data['destination_name_en'],
                'iata_code': self.cleaned_data['iata_code'],
                'icao_code': self.cleaned_data.get('icao_code', ''),  # Если пусто, то используем ''
            }
        )

        # Создаем объект FlightForTemplate
        instance = super().save(commit=False)
        instance.airline = airline
        instance.flight = flight
        instance.destination = destination

        if commit:
            instance.save()

        return instance


