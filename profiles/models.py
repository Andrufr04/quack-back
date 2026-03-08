import uuid
from django.db import models
from django.conf import settings

class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    patronymic = models.CharField(max_length=100, null=True, blank=True)
    birthdate = models.DateField()

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True)
    
    profile_picture = models.ImageField(upload_to='avatars/', null=True, blank=True)
    banner_picture = models.ImageField(upload_to='banners/', null=True, blank=True)