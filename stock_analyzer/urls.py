from django.contrib import admin
from django.urls import path
from stock_analyzer import views

urlpatterns = [
    path("", views.index, name='home'),
    path("api/live-stock/", views.live_stock_data, name="live_stock_data"),
    path("market_trends/", views.market_trends, name='market_trends'),
    path("prediction/", views.prediction_view, name='prediction_view'),
    path('api/autocomplete/', views.ticker_autocomplete, name='ticker_autocomplete'),
    path("about/", views.about, name='about'),
    path('register/', views.register, name='register'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('logout/', views.logout_user, name='logout'),
    path('watchlist/', views.watchlist, name='watchlist'),
    path('add-watchlist/', views.add_watchlist, name='add_watchlist'),
    path('remove-watchlist/<int:stock_id>/', views.remove_watchlist, name='remove_watchlist'),
    path("create-alert/", views.create_alert, name="create_alert"),
    path("notifications/", views.notifications, name="notifications"),
    path("api/notifications/", views.get_notifications),
    path("mark-notifications-read/", views.mark_notifications_read, name="mark_notifications_read"),
    path("delete-notification/<int:notif_id>/", views.delete_notification, name="delete_notification"),
    path('poll-notifications/', views.notification_poll, name='poll_notifications'),
    path('api/live-notifications/', views.check_live_notifications, name='live_notifications_api'),
    path('ai-copilot/', views.ai_agent_copilot, name='ai_agent_copilot'),
]