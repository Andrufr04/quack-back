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
    study_group = models.ForeignKey(StudyGroup, on_delete=models.SET_NULL, null=True, blank=True)
    coins = models.IntegerField(default=0)
    ducks = models.IntegerField(default=0)

class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)

class Teacher(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(Person, on_delete=models.CASCADE)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='qualified_teachers')

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
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField()
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

class LessonType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name='lessons')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lessons')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    theme = models.CharField(max_length=200, blank=True, null=True) 
    lesson_type = models.ForeignKey(LessonType, on_delete=models.SET_NULL, null=True, blank=True) 
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    classroom = models.CharField(max_length=50, default="Онлайн")
    
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='scheduled_lessons')

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.subject.name} - {self.study_group.name}"

class Attendance(models.Model):
    ATTENDANCE_CHOICES = [
        (0, 'absnt'),
        (1, 'present'),
        (2, 'late'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    status = models.IntegerField(choices=ATTENDANCE_CHOICES, default=1)

    class Meta:
        unique_together = ('lesson', 'student')

class LessonDuck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='ducks_given')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('lesson', 'student')

class LessonMark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='marks')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='lesson_marks')
    grade = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('lesson', 'student') # Одна оцінка для студента за одну пару

class News(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    text = models.TextField(max_length=4096)
    image = models.ImageField(upload_to='news/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class NewsReadStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name='read_statuses')
    
    # 🔥 Зв'язуємо саме з твоєю моделлю Student
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='read_news') 
    
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('news', 'student')