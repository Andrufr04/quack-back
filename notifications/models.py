import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    CATEGORY_CHOICES = (
        ('education', 'edu'),
        ('social', 'soc'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='education')
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    related_object_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']