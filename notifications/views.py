from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

class NotificationPagination(PageNumberPagination):
    page_size = 50 # Завантажуємо по 50 штук
    page_size_query_param = 'page_size'
    max_page_size = 100

# 2. Оновлюємо в'юху списку
class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Отримуємо тільки сповіщення поточного юзера
        queryset = Notification.objects.filter(recipient=self.request.user)
        
        # 🔥 Фільтруємо за категорією, якщо фронт передав ?category=...
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
            
        return queryset


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # Шукаємо сповіщення, яке належить ТІЛЬКИ поточному юзеру
        notification = get_object_or_404(Notification, id=pk, recipient=request.user)
        
        if not notification.is_read:
            notification.is_read = True
            notification.save()
            
        return Response({"status": "read"})


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Оновлюємо всі непрочитані сповіщення юзера одним SQL-запитом (це дуже швидко)
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"status": "all_read"})