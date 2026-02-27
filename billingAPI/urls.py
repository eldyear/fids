# billing_api/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_billing_data, name='get_billing_data'),
    # path('display-from-json/', views.display_billing_data_from_json, name='display_from_json'),
]