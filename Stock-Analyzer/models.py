from django.db import models
from django.contrib.auth.models import User


class Watchlist(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    stock_symbol = models.CharField(
        max_length=20
    )

    def __str__(self):
        return f"{self.user.username} - {self.stock_symbol}"


class PriceAlert(models.Model):

    CONDITION_CHOICES = [("above", "Above"),("below", "Below")]

    user = models.ForeignKey(User,on_delete=models.CASCADE)

    stock_symbol = models.CharField(max_length=20)

    target_price = models.FloatField()

    condition = models.CharField(
        max_length=10,
        choices=CONDITION_CHOICES
    )

    is_active = models.BooleanField(default=True)

    triggered = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):

        return (
            f"{self.stock_symbol} "
            f"{self.condition} "
            f"{self.target_price}"
        )


class Notification(models.Model):

    user = models.ForeignKey(User,on_delete=models.CASCADE)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message