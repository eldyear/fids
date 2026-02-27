from django.urls import path
from . import views

urlpatterns = [
    path('', views.flight_list, name='flight_list'),
    path('select/', views.select_flight, name='select_flight'),
    path('scan/<int:flight_id>/', views.scan_baggage, name='scan_baggage'),
    path('search/', views.search_baggage, name='search_baggage'),
    path('flight_details/<int:flight_id>/', views.flight_details, name='flight_details'),
    path('flight_details/<int:flight_id>/generate_pdf/', views.generate_pdf_report, name='generate_pdf_report'),
    path('container/close/<int:container_id>/', views.close_container, name='close_container'),
    # path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout')
]