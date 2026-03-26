from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification # або звідки ти імпортуєш модель

def create_and_send_notification(recipient, title, message, category='education', related_id=None):
    # 1. Зберігаємо в базу (щоб була історія)
    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        category=category,
        related_object_id=related_id
    )

    # 2. Відправляємо в особистий сокет юзера
    channel_layer = get_channel_layer()
    room_name = f'user_{recipient.id}'
    
    payload = {
        'id': str(notification.id),
        'title': notification.title,
        'message': notification.message,
        'category': notification.category,
        'created_at': notification.created_at.isoformat(),
        'is_read': False,
        'related_object_id': related_id
    }

    async_to_sync(channel_layer.group_send)(
        room_name,
        {
            'type': 'send_notification',
            'payload': payload
        }
    )