# scanner_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # path('dashboard/', views.barcode_scanner_dashboard, name='barcode_scanner_dashboard'), # Если вам нужна панель мониторинга Django
    path('', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    path('save_scan/', views.save_barcode_scan, name='save_barcode_scan'),
    path('dashboard/', views.get_barcode_scan, name='get_barcode_scan'),
    path('all_scans/', views.all_scans_view, name='all_scans_view'),
    path('api/scans/', views.get_all_scans_api, name='get_all_scans_api'),
    # Reports page
    path('reports/', views.reports_view, name='reports_view'),
    path('reports/export/excel/', views.export_to_excel, name='export_to_excel'),
    path('reports/export/pdf/', views.export_to_pdf, name='export_to_pdf'),
]