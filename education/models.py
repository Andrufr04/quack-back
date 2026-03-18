import os
import uuid
from django.db import models
from django.conf import settings
from profiles.models import Person

def attachment_upload_path(instance, filename):
    return os.path.join('attachments', str(instance.group.id), filename)

class AttachmentGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

class AttachmentFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(AttachmentGroup, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to=attachment_upload_path)

class StudyGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    curator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_groups', limit_choices_to={'groups__name': "Curator"})

class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(Person, on_delete=models.CASCADE)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE)

class Teacher(models.Model): #todo:remove
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(Person, on_delete=models.CASCADE)
    teaching_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE)

class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)

class TaskType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tasks')
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    theme = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    task_type = models.ForeignKey(TaskType, on_delete=models.SET_NULL, null=True, blank=True)
    start = models.DateField(auto_now_add=True)
    end = models.DateField()
    attachments = models.ForeignKey(AttachmentGroup, on_delete=models.SET_NULL, null=True, blank=True)

class TaskStatus(models.Model):
    STATUS_CHOICES = [
        (0, 'task.inprogress'),
        (1, 'task.oncheck'),
        (2, 'task.checked'),
        (3, 'task.deleted')
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)

    class Meta:
        unique_together = ('task', 'student')

class TaskOnCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    text = models.TextField(null=True, blank=True)
    attachments = models.ForeignKey(AttachmentGroup, on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

class TaskChecked(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    mark = models.IntegerField()
    comment = models.TextField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name='lessons')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lessons')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    lesson_type = models.ForeignKey(TaskType, on_delete=models.SET_NULL, null=True, blank=True) # Напр. "Лекція"
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    classroom = models.CharField(max_length=50, default="Онлайн")
    
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduled_lessons')

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.subject.name} - {self.study_group.name}"