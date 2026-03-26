from django.urls import path
from . import views

urlpatterns = [
    # GET /api/notifications/
    path('', views.NotificationListView.as_view(), name='notification-list'),
    
    # POST /api/notifications/<id>/read/
    path('<uuid:pk>/read/', views.MarkNotificationReadView.as_view(), name='notification-read'),
    
    # POST /api/notifications/read-all/
    path('read-all/', views.MarkAllNotificationsReadView.as_view(), name='notification-read-all'),
]