# context_processors.py
from .models import Notification

def notification_context(request):
    # If the user is anonymous or not authenticated, return empty defaults safely!
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'notifications': [],
            'unread_count': 0
        }
    
    try:
        notifications = Notification.objects.filter(user=request.user).order_by("-created_at")[:20]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {
            'notifications': list(notifications),
            'unread_count': unread_count
        }
    except Exception:
        return {
            'notifications': [],
            'unread_count': 0
        }