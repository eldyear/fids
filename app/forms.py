from django import forms
from datetime import date

class SelectDateForm(forms.Form):
    selected_date = forms.DateField(
        widget=forms.SelectDateWidget(attrs={'class': 'form-control'}),
        label="Выберите дату для формирования",
        initial=date.today  # Устанавливаем текущую дату по умолчанию
    )