from django.contrib import admin
from django.urls import path
from Home import views

urlpatterns = [
    path("", views.index, name='home'),
    path("market_trends/", views.market_trends, name='market_trends'),
    path("prediction/", views.prediction_view, name='prediction'),
    path("portfolio/", views.portfolio, name='portfolio'),
    path("about/", views.about, name='about'),
]