from django.urls import re_path, path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from .forms import CustomAuthenticationForm
from .views import (
    generate_daily_schedule_view,
    FlightTemplateListView, 
    FlightTemplateCreateView, 
    FlightTemplateUpdateView,
    FlightTemplateDeleteView,
    user_menu,
    FlightForTemplateCreateView,
    export_daily_plan_to_docx,
    import_flights_view,
    AirlineListView, AirlineCreateView, AirlineUpdateView,
    CityListView, CityCreateView, CityUpdateView,
    GateListView, GateCreateView, GateUpdateView,
    DeskListView, DeskCreateView, DeskUpdateView,
    update_flight_inline
)

urlpatterns = [
    path('user_menu/', user_menu, name='user_menu'),
    # path('flights/last-7-months-chart/', views.FlightsLast7MonthsChartView.as_view(), name='flights_last_7_months_chart'),
    path('inftablo/', views.InfTabloListView.as_view(), name='inftablo_list'),
    path('inftablo/add/', views.InfTabloCreateView.as_view(), name='inftablo_add'),
    path('inftablo/<int:pk>/edit/', views.InfTabloUpdateView.as_view(), name='inftablo_edit'),
    path('inftablo/update_status/', views.update_status, name='update_status'),
    path('inftablo/delete/<int:pk>/', views.InfTabloDeleteView.as_view(), name='inftablo_delete'),

    path('generate-daily-schedule/', generate_daily_schedule_view, name='generate_daily_schedule'),

    path('flight-templates/', FlightTemplateListView.as_view(), name='flight_template_list'),
    path('flight-templates/add/', FlightTemplateCreateView.as_view(), name='flight_template_add'),
    path('flight-templates/edit/<int:pk>/', FlightTemplateUpdateView.as_view(), name='flight_template_edit'),
    path('flight-templates/delete/<int:pk>/', FlightTemplateDeleteView.as_view(), name='flight_template_delete'),
    path('add_flights/', FlightForTemplateCreateView.as_view(), name='add_flights'),
    path('search_flights/', views.search_flights, name='search_flights'),

    path('export/daily_plan/docx/', views.export_daily_plan_to_docx, name='export_daily_plan_to_docx'),
    path('export/daily_plan/xlsx/', views.export_daily_plan_to_xlsx, name='export_daily_plan_xlsx'),
    path('export/daily_plan/pdf/', views.export_daily_plan_to_pdf, name='export_daily_plan_pdf'),

    path('import_flights/', import_flights_view, name='import_flights'),
    path('update_flight_inline/<int:pk>/', update_flight_inline, name='update_flight_inline'),

    # Airlines
    path('airlines/', AirlineListView.as_view(), name='airline_list'),
    path('airlines/add/', AirlineCreateView.as_view(), name='airline_add'),
    path('airlines/edit/<int:pk>/', AirlineUpdateView.as_view(), name='airline_edit'),

    # Cities
    path('cities/', CityListView.as_view(), name='city_list'),
    path('cities/add/', CityCreateView.as_view(), name='city_add'),
    path('cities/edit/<int:pk>/', CityUpdateView.as_view(), name='city_edit'),

    # Gates
    path('gates/', GateListView.as_view(), name='gate_list'),
    path('gates/add/', GateCreateView.as_view(), name='gate_add'),
    path('gates/edit/<int:pk>/', GateUpdateView.as_view(), name='gate_edit'),

    # Desks
    path('desks/', DeskListView.as_view(), name='desk_list'),
    path('desks/add/', DeskCreateView.as_view(), name='desk_add'),
    path('desks/edit/<int:pk>/', DeskUpdateView.as_view(), name='desk_edit'),

    # path('', LoginView.as_view(authentication_form=CustomAuthenticationForm, next_page='user_menu'), name='login'),
    re_path('', auth_views.LoginView.as_view(template_name='users/login.html', next_page='user_menu'), name='login'),
     path('logout/', views.logout_view, name='logout'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    # path('flights/last-7-months/', views.flights_last_7_months, name='flights_last_7_months'),

]
