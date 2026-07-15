"""
URL configuration for Hello project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import stock_analizer
    2. Add a URL to urlpatterns:  path('', stock_analyzer.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Home app URLs
    path('', include('stock_analyzer.urls')),

    # Authentication
    path('login/',auth_views.LoginView.as_view(template_name='login.html'),name='login'),

    path('logout/',auth_views.LogoutView.as_view(),name='logout'),
    
]