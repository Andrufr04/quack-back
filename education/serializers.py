from rest_framework import serializers
from .models import Lesson, Task, Subject, TaskType

class TaskSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    task_type_name = serializers.CharField(source='task_type.name', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 
            'subject_name', 
            'task_type_name', 
            'theme', 
            'description', 
            'start', 
            'end'
        ]

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = '__all__' # Або перелічи конкретні поля: ['teacher', 'classroom', 'start_time', 'end_time']