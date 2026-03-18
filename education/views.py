from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from rest_framework import generics

from education.serializers import LessonSerializer
from django.contrib.auth import get_user_model

from .models import (
    Lesson, Task, TaskStatus, TaskOnCheck, TaskChecked, Teacher, 
    Student, StudyGroup, Subject, AttachmentGroup, AttachmentFile, TaskType
)
from users.permissions import IsAdministration, IsTeacher, IsStudent, IsCurator

User = get_user_model()

class CreateTaskView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        with transaction.atomic():
            # 1. Обробка файлів
            files = request.FILES.getlist('attachments')
            att_group = None
            if files:
                att_group = AttachmentGroup.objects.create()
                for f in files:
                    AttachmentFile.objects.create(group=att_group, file=f)

            # 2. Створення Task
            task = Task.objects.create(
                author=request.user,
                study_group_id=request.data.get('study_group'),
                subject_id=request.data.get('subject'),
                task_type_id=request.data.get('task_type') or None,
                theme=request.data.get('theme'),
                description=request.data.get('description'),
                end=request.data.get('deadline'),
                attachments=att_group
            )

            # 3. Розсилка статусів студентам групи
            students = Student.objects.filter(study_group_id=task.study_group_id)
            TaskStatus.objects.bulk_create([
                TaskStatus(task=task, student=student, status=0) for student in students
            ])
            
            return Response({"id": task.id}, status=status.HTTP_201_CREATED)
        
class TeacherGroupsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]
    
    def get(self, request):
        # Отримуємо вчителя через його Person та User
        try:
            teacher = Teacher.objects.get(person__user=request.user)
            group = teacher.teaching_group
            # Повертаємо масив, навіть якщо там одна група, щоб фронтенд працював універсально
            return Response([{"id": group.id, "name": group.name}])
        except Teacher.DoesNotExist:
            return Response([], status=404)

class TasksTypeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        task_types = TaskType.objects.all()
        data = [{"id": str(t.id), "name": t.name} for t in task_types]
        return Response(data, status=status.HTTP_200_OK)

class TeacherSubjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = request.user.groups.filter(name='Administration').exists()
        group_id = request.query_params.get('group_id')

        if is_admin:
            subjects = Subject.objects.all()
        else:
            if not group_id:
                return Response([], status=200)
            
            subjects = Subject.objects.all() 

        data = [{"id": str(s.id), "name": s.name} for s in subjects]
        return Response(data)
    
class TeacherPendingTasksView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]
    
    def get(self, request):
        group_name = request.query_params.get('group')
        
        # Фільтруємо за автором (вчителем)
        submissions = TaskOnCheck.objects.filter(task__author=request.user).select_related(
            'student__person', 'student__group', 'task__subject'
        )
        
        if group_name and group_name != "Всі":
            submissions = submissions.filter(student__group__name=group_name)

        output = []
        for s in submissions:
            output.append({
                "id": str(s.id),
                "student_name": f"{s.student.person.name} {s.student.person.surname}",
                "group_name": s.student.group.name if s.student.group else "Без групи",
                "task_theme": s.task.theme,
                "submitted_at": s.submitted_at.isoformat(),
                "text": s.text,
                "attachments": { # Якщо є вкладення
                     "id": str(s.attachments.id),
                     "files": [{"id": str(f.id), "file": request.build_absolute_uri(f.file.url)} for f in s.attachments.files.all()]
                } if s.attachments else None,
                "task": { # ЦЕ ТЕ, ЩО МИ ДОДАВАЛИ В ІНТЕРФЕЙС
                    "id": str(s.task.id),
                    "theme": s.task.theme,
                    "subject_name": s.task.subject.name,
                    "description": s.task.description,
                    "start": s.task.start.isoformat(),
                    "end": s.task.end.isoformat(),
                }
            })
        return Response(output)
    

class GradeTaskView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request, submission_id):
        submission = get_object_or_404(TaskOnCheck, id=submission_id)
        
        mark = request.data.get('mark')
        comment = request.data.get('comment', '')

        if mark is None:
            return Response({"error": "Mark is required"}, status=400)

        with transaction.atomic():
            # Створюємо запис БЕЗ аргументу teacher, бо його немає в моделі
            TaskChecked.objects.create(
                task=submission.task,
                student=submission.student,
                mark=mark,
                comment=comment
            )
            
            # Оновлюємо статус на "Перевірено"
            TaskStatus.objects.filter(
                task=submission.task, 
                student=submission.student
            ).update(status=2)
            
            # Видаляємо з черги на перевірку
            submission.delete()
            
            return Response({"status": "graded"}, status=201)
        

class StudentTasksView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    
    def get(self, request):
        status_filter = request.query_params.get('status', 0)
        try:
            student = Student.objects.get(person__user=request.user)
            tasks = TaskStatus.objects.filter(
                student=student, 
                status=status_filter
            ).select_related('task', 'task__author', 'task__subject', 'task__task_type', 'task__attachments')
            
            output = []
            for s in tasks:
                task_obj = s.task
                attachments_data = None

                if task_obj.attachments:
                    files_list = []
                    for f in task_obj.attachments.files.all():
                        url = request.build_absolute_uri(f.file.url)
                        
                        if not settings.DEBUG and url.startswith('http://'):
                            url = url.replace('http://', 'https://', 1)
                            
                        files_list.append({
                            "id": str(f.id),
                            "file": url
                        })

                    attachments_data = {
                        "id": str(task_obj.attachments.id),
                        "files": files_list
                    }

                task_data = {
                    "id": str(s.id),
                    "task": {
                        "id": str(task_obj.id),
                        "theme": task_obj.theme,
                        "author_name": task_obj.author.get_full_name() or task_obj.author.username,
                        "subject_name": task_obj.subject.name,
                        "description": task_obj.description or "",
                        "task_type_name": task_obj.task_type.name if task_obj.task_type else None,
                        "start": task_obj.start.isoformat() if task_obj.start else None,
                        "end": task_obj.end.isoformat() if task_obj.end else None,
                        "attachments": attachments_data
                    },
                    "status": s.status,
                    "mark": None,
                    "comment": None
                }

                if s.status == 2:
                    check_info = TaskChecked.objects.filter(task=task_obj, student=student).first()
                    if check_info:
                        task_data["mark"] = check_info.mark
                        task_data["comment"] = check_info.comment

                output.append(task_data)
            return Response(output)

        except Exception as e:
            print(f"ERROR: {str(e)}") 
            return Response({"error": "Внутрішня помилка сервера"}, status=500)

class SubmitTaskWorkView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    
    def post(self, request):
        with transaction.atomic():
            # Отримуємо студента
            student = get_object_or_404(Student, person__user=request.user)
            task_id = request.data.get('task_id')
            
            # Перевір, що саме шле фронт! 
            # Якщо в логах було "file", то використовуй 'file'
            files = request.FILES.getlist('file') or request.FILES.getlist('attachments')
            
            att_group = None
            if files:
                # Створюємо групу вкладень
                att_group = AttachmentGroup.objects.create()
                for f in files:
                    AttachmentFile.objects.create(group=att_group, file=f)

            # Створюємо запис на перевірку
            TaskOnCheck.objects.create(
                task_id=task_id,
                student=student,
                text=request.data.get('text', ''),
                attachments=att_group  # Тепер тут буде ID групи, якщо файли були
            )

            # Оновлюємо статус на 1 (На перевірці)
            TaskStatus.objects.filter(
                task_id=task_id, 
                student=student
            ).update(status=1)

            return Response({"status": "submitted"}, status=status.HTTP_201_CREATED)
        
class TeacherTasksToCheckView(APIView):
    permission_classes = [IsAuthenticated] 

    def get(self, request):
        try:
            group_name = request.query_params.get('group')
            
            query = TaskOnCheck.objects.filter(
                task__author=request.user
            ).select_related(
                'student__person__user', 
                'student__study_group', 
                'task__subject',
                'attachments'
            )

            if group_name and group_name != "Всі":
                query = query.filter(student__study_group__name=group_name)

            output = []

            for work in query:
                # Виправлений блок обробки файлів студента
                attachments_data = None
                if work.attachments:
                    files_list = []
                    for f in work.attachments.files.all():
                        file_url = request.build_absolute_uri(f.file.url)
                        # Фікс Mixed Content
                        if '127.0.0.1' not in file_url and 'localhost' not in file_url:
                            if 'quackdemo.duckdns.org' in file_url:
                                file_url = file_url.replace('http://', 'https://')
                        
                        files_list.append({
                            "id": str(f.id),
                            "file": file_url
                        })
                    
                    attachments_data = {
                        "id": str(work.attachments.id),
                        "files": files_list
                    }

                s = work.student
                student_display_name = s.person.get_full_name() if (s and s.person) else s.person.user.username
                group_display_name = s.study_group.name if (s and s.study_group) else "Без групи"

                output.append({
                    "id": str(work.id),
                    "student_name": student_display_name,
                    "group_name": group_display_name,
                    "submitted_at": work.submitted_at.isoformat(),
                    "text": work.text or "",
                    "task_theme": work.task.theme,
                    "subject_name": work.task.subject.name,
                    "attachments": attachments_data,
                    "task": {
                        "id": str(work.task.id),
                        "theme": work.task.theme,
                        "subject_name": work.task.subject.name,
                        "description": work.task.description or "",
                        "start": work.task.start.isoformat() if work.task.start else None,
                        "end": work.task.end.isoformat() if work.task.end else None,
                    }
                })

            return Response(output)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({"error": str(e)}, status=500)
        
class TeacherCurrentLessonView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        now = timezone.now()
        
        current_lesson = Lesson.objects.filter(
            teacher=request.user,
            start_time__lte=now,
            end_time__gte=now
        ).select_related('subject', 'study_group', 'lesson_type').first()

        if current_lesson:
            return self._get_lesson_response(current_lesson, is_current=True)

        # 2. Якщо зараз пари немає, шукаємо НАЙБЛИЖЧУ майбутню
        next_lesson = Lesson.objects.filter(
            teacher=request.user,
            start_time__gt=now
        ).select_related('subject', 'study_group', 'lesson_type').order_by('start_time').first()

        if next_lesson:
            return self._get_lesson_response(next_lesson, is_current=False)

        return Response({"detail": "No lessons scheduled"}, status=200)

    def _get_lesson_response(self, lesson, is_current):
        # Отримуємо список студентів групи
        students = Student.objects.filter(study_group=lesson.study_group).select_related('person')
        students_data = [
            {"id": str(s.id), "name": f"{s.person.name} {s.person.surname}"} 
            for s in students
        ]

        return Response({
            "is_current": is_current,
            "lesson": {
                "id": str(lesson.id),
                "subject": lesson.subject.name,
                "type": lesson.lesson_type.name if lesson.lesson_type else "Заняття",
                "group": lesson.study_group.name,
                "start": lesson.start_time.isoformat(),
                "end": lesson.end_time.isoformat(),
                "classroom": lesson.classroom,
                "students": students_data
            }
        })
    
class LessonListFilteringView(generics.ListAPIView):
    """Отримання списку пар з фільтрами для адміна"""
    permission_classes = [IsAuthenticated, IsAdministration]
    
    def get_queryset(self):
        queryset = Lesson.objects.all().select_related('study_group', 'teacher', 'subject', 'lesson_type')
        teacher_id = self.request.query_params.get('teacher')
        group_id = self.request.query_params.get('group')

        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        if group_id:
            queryset = queryset.filter(study_group_id=group_id)
        
        return queryset.order_by('start_time')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = []
        for l in queryset:
            data.append({
                "id": str(l.id),
                "group_name": l.study_group.name,
                "teacher_name": l.teacher.get_full_name() or l.teacher.username,
                "subject_name": l.subject.name,
                "start": l.start_time.isoformat(),
                "end": l.end_time.isoformat(),
                "classroom": l.classroom,
                "teacher_id": str(l.teacher.id),
                "group_id": str(l.study_group.id)
            })
        return Response(data)

class LessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Видалення або зміна конкретної пари"""
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer  # <--- ДОДАЙ ЦЕ
    permission_classes = [IsAuthenticated, IsAdministration]
    # DRF сам зробить update (PUT/PATCH) та destroy (DELETE)
        
class CreateLessonView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def post(self, request):
        # Отримуємо дані з запиту
        group_id = request.data.get('study_group')
        teacher_id = request.data.get('teacher')
        subject_id = request.data.get('subject')
        type_id = request.data.get('lesson_type')
        start = request.data.get('start_time')
        end = request.data.get('end_time')
        classroom = request.data.get('classroom', 'Онлайн')
        task_id = request.data.get('task_id')

        lesson = Lesson.objects.create(
            study_group_id=group_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
            lesson_type_id=type_id if type_id else None,
            start_time=start,
            end_time=end,
            classroom=classroom,
            task_id=task_id if task_id else None
        )

        return Response({"id": lesson.id, "status": "Lesson created"}, status=201)

# Також знадобиться список усіх вчителів для вибору в селекті
class AllTeachersView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]
    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        teachers = User.objects.filter(groups__name='teacher')
        data = [{"id": t.id, "name": t.get_full_name()} for t in teachers]
        return Response(data)

# І список усіх груп
class AllGroupsView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]
    def get(self, request):
        groups = StudyGroup.objects.all()
        return Response([{"id": g.id, "name": g.name} for g in groups])

class AdminStudyGroupView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def get(self, request):
        # 1. Отримуємо групи
        groups = StudyGroup.objects.select_related('curator__person').all().order_by('name')
        groups_data = [{
            "id": str(g.id),
            "name": g.name,
            "curator_id": str(g.curator.id) if g.curator else None,
            "curator_name": g.curator.person.get_full_name() if g.curator and hasattr(g.curator, 'person') else "Не призначено"
        } for g in groups]

        # 2. Отримуємо список усіх кураторів для селектора
        curators = User.objects.filter(groups__name="сurator").select_related('person')
        curators_data = [{
            "id": str(c.id),
            "full_name": c.person.get_full_name() if hasattr(c, 'person') else c.email
        } for c in curators]

        return Response({
            "groups": groups_data,
            "available_curators": curators_data
        })

    def post(self, request):
        name = request.data.get('name')
        curator_id = request.data.get('curator_id')
        
        group = StudyGroup.objects.create(
            name=name,
            curator_id=curator_id if curator_id else None
        )
        return Response({"status": "created"}, status=201)

    def patch(self, request, pk):
        group = get_object_or_404(StudyGroup, pk=pk)
        if 'name' in request.data:
            group.name = request.data['name']
        if 'curator_id' in request.data:
            group.curator_id = request.data['curator_id'] or None
            
        group.save()
        return Response({"status": "updated"})