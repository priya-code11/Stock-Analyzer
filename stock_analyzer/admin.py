from django.contrib import admin
from .models import Watchlist, PriceAlert, Notification

admin.site.register(Watchlist)
admin.site.register(PriceAlert)
admin.site.register(Notification)