# flights/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # --- Десктопная версия ---
    path('supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    
    # 1. Маршрут для создания новой техкарты
    path('supervisor/manage_services/<int:flight_id>/services/', views.manage_services_for_flight, name='manage_services'),
    
    # 2. Маршрут для просмотра/редактирования существующей техкарты
    path('supervisor/manage_services/<int:flight_id>/services/<int:tech_card_id>/', views.manage_services_for_flight, name='view_services'),
    # path('update/<int:flight_id>/<str:field_name>/', views.update_flight_field, name='update_flight_field'),
    path('update-flight-field/', views.update_flight_field, name='update_flight_field'),
    path('supervisor/delete_service/<int:service_id>/', views.delete_service, name='delete_service'),
    path('supervisor/techcards/<int:tech_card_id>/update_field/', views.update_techcard_field, name='update_techcard_field'),
    # path('update_flight_field/<int:flight_id>/<str:field_name>/', views.update_flight_field, name='update_flight_field'),
    # path('get_flights_for_linking/', views.get_flights_for_linking, name='get_flights_for_linking'),
    path('get_flights_for_linking/', views.get_flights_for_linking, name='get_flights_for_linking'),

    path('supervisor/techcards/<int:tech_card_id>/close/', views.close_techcard, name='close_techcard'),

    # --- Мобильная версия ---
    path('dashboard/mobile/', views.supervisor_dashboard_mobile, name='supervisor_dashboard_mobile'),
    path('manage_services_mobile/<int:flight_id>/', views.manage_services_mobile, name='create_services_mobile'),
    path('manage_services_mobile/<int:flight_id>/<int:tech_card_id>/', views.manage_services_mobile, name='manage_services_mobile'),
    path('view_services_mobile/<int:flight_id>/<int:tech_card_id>/', views.view_services_mobile, name='view_services_mobile'),
    path('delete_service/<int:service_id>/mobile/', views.delete_service_mobile, name='delete_service_mobile'),
    # path('create_tech_card_mobile/<int:flight_id>/', views.create_tech_card_mobile, name='create_tech_card_mobile'),
    # --- URL-адреса авторизации (общие) ---
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('login/mobile/', auth_views.LoginView.as_view(
        template_name='registration/login_mobile.html',
        next_page=reverse_lazy('supervisor_dashboard_mobile')
    ), name='login_mobile'),
    path('logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('login_mobile')), name='logout'),
    
    # --- Экспорт и отчёты ---
    path('export/<int:flight_id>/techcard/<int:tech_card_id>/', views.export_to_pdf, name='export_to_pdf'),
    path('preview/<int:flight_id>/techcard/<int:tech_card_id>/', views.export_to_pdf, name='preview_pdf_template'),
    path('export_to_pdf/<int:flight_id>/<int:tech_card_id>/', views.export_to_pdf, name='export_to_pdf_old'), # Устаревший, но оставлен для совместимости
    path('preview_pdf_template/<int:flight_id>/<int:tech_card_id>/', views.preview_pdf_template, name='preview_pdf_template_old'), # Устаревший
    
    # --- Финансовый модуль ---
    path('finance/', views.finance_dashboard, name='finance_dashboard'),
    path('finance/prices/', views.price_management, name='price_management'),
    path('finance/prices/save/', views.save_price, name='save_price'),
    path('finance/manage/<int:flight_id>/<int:tech_card_id>/', views.finance_manage_services, name='finance_manage_services'),
    path('finance/manage_services/<int:flight_id>/export/pdf/', views.finance_export_to_pdf, name='finance_export_to_pdf'),
    path('finance/manage_services/<int:flight_id>/export/excel/', views.export_to_excel, name='export_to_excel'),
    path('finance/manage_services/<int:flight_id>/export/1c/', views.export_to_1c, name='export_to_1c'),
    
    # --- Логи ---
    path('logs/', views.log_list, name='log_list'),

    # --- НОВЫЕ МАРШРУТЫ ДЛЯ DASHBOARD ---
    # path('/v2/', views.dashboard_v2, name='dashboard_v2'),
    # path('dashboard/v2/get_services/<int:tech_card_id>/', views.get_services_for_tech_card, name='get_services_for_tech_card'),
    # ------------------------------------
]