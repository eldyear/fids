"""
URL configuration for oss project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path,include, re_path
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.contrib.auth import views as auth_views


@staff_member_required
def custom_links_view(request):
    return render(request, "admin/custom_links.html")

urlpatterns = [
    path('', include('app.urls')),
    path('users/', include('users.urls')),
    # path('badge/', include('IDbadge.urls')),
    path('billing/', include('billing.urls')),
    path('admin/', admin.site.urls),
    path('scanner/', include('scanner_app.urls')),
    path('api/billing/', include('billingAPI.urls')),
    path('bagscan/', include('barbag.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)