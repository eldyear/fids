from django.urls import path
from . import views1
from . import admin
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('tablo_dep/<str:lang>/', views1.tablo_dep, name='tablo_dep'),
    path('tablo_arr/<str:lang>/', views1.tablo_arr, name='tablo_arr'),
    path('dep/', views1.departure, name='departure'),
    path('arr/', views1.arrival, name='arrival'),
    path('iframe_dep/', views1.iframe_dep, name='iframe_dep'),
    path('iframe_arr/', views1.iframe_arr, name='iframe_arr'),
    path('deparr/', views1.deparr, name='deparr'),
    path('st/<int:pk>/', views.check_ajax, name='check_in_desk_ajax'),
    path('gate/<int:pk>/', views1.gate, name='gate'),
    path('bag/<int:pk>/', views1.baggage, name='baggage'),
    path('main/', views1.my_urls, name='main'),
    path('get_flight_data_check/<str:lang>/<int:pk>/', views1.get_flight_data_check, name='get_flight_data_check'),
    path('get_flight_data_gate/<str:lang>/G<int:pk>/', views1.get_flight_data_gate, name='get_flight_data_gate'),
    path('get_flight_data_bag/<str:lang>/<int:pk>/', views1.get_flight_data_bag, name='get_flight_data_bag'),
    path('generate-daily-schedule/', admin.generate_daily_schedule_view, name='generate_daily_schedule'),
    path("update_flights/", views.update_flights, name="update_flights"),
    # path('confirm-delay-ajax/', views1.confirm_delay_ajax, name='confirm_delay_ajax'),
    path('update_sky_priority/<int:flight_id>/', views1.update_sky_priority, name='update_sky_priority'),
    path("update_stoika/<int:flight_id>/", views1.update_stoika, name="update_stoika"),
    path("update_gate/<int:flight_id>/", views1.update_gate, name="update_gate"),
    path("update_baggage/<int:flight_id>/", views1.update_baggage, name="update_baggage"),
    path('update_log/', views1.update_log, name='update_log'),
    path('', views1.my_urls, name='main'),

    # Новые маршруты для агентов
    path('stagent/<str:stand_number>/', views.agent_registration_view, name='agent_registration_view'),
    path('gtagent/<str:gate_number>/', views.agent_boarding_view, name='agent_boarding_view'),

    # Новые API-эндпоинты для действий агентов
    path('api/start_registration/', views.start_registration_api, name='start_registration_api'),
    path('api/end_registration/', views.end_registration_api, name='end_registration_api'),
    path('api/start_boarding/', views.start_boarding_api, name='start_boarding_api'),
    path('api/end_boarding/', views.end_boarding_api, name='end_boarding_api'),

    # Новый API для получения активных регистраций
    path('api/active-registrations/<str:lang>/', views.get_active_registrations_api, name='active_registrations_api'),
    path('api/active_registrations', views.get_active_registrations_api, name='active_registrations_api'),
    path('flights_table/', views.flight_table_view, name='flight_table'),
]
