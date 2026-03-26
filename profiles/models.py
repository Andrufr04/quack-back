import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

def post_image_path(instance, filename):
    ext = filename.split('.')[-1]
    return f'posts/{uuid.uuid4().hex}.{ext}'

class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    patronymic = models.CharField(max_length=100, null=True, blank=True)
    birthdate = models.DateField()

    def get_full_name(self):
        return f"{self.name} {self.surname}"

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    description = models.CharField(max_length=512, null=True, blank=True)
    
    profile_picture = models.ImageField(upload_to='avatars/', null=True, blank=True)
    banner_picture = models.ImageField(upload_to='banners/', null=True, blank=True)

class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    
    title = models.CharField(max_length=255, null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    # 🔥 ПОЛЕ image ЗВІДСИ ВИДАЛЯЄМО!
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

# 🔥 НОВА ТАБЛИЦЯ ДЛЯ КАРТИНОК 🔥
class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=post_image_path)

class Reaction(models.Model):
    EMOJI_CHOICES = [
        ('👍', 'Like'),
        ('🔥', 'Fire'),
        ('❤️', 'Love'),
        ('😂', 'Haha'),
        ('🤯', 'Wow'),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10, choices=EMOJI_CHOICES)

    class Meta:
        unique_together = ('post', 'user')