from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Task, Student
from .serializers import TaskSerializer

class StudentTasksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = Student.objects.get(person__user=request.user)
            tasks = Task.objects.filter(study_group=student.study_group).order_by('end')
            
            serializer = TaskSerializer(tasks, many=True)
            return Response(serializer.data)
        except Student.DoesNotExist:
            return Response({"error": "Студента не знайдено"}, status=404)