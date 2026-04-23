from django.forms import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from rest_framework import generics
from django.db.models import Avg, Sum, Value, FloatField, Subquery, OuterRef, Exists
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework.parsers import MultiPartParser, FormParser

from education.serializers import LessonSerializer
from django.contrib.auth import get_user_model

from notifications.services import create_and_send_notification

from .models import (
    Attendance, Lesson, LessonDuck, LessonMark, LessonType, News, NewsReadStatus, Task, TaskStatus, TaskOnCheck, TaskChecked, Teacher, 
    Student, StudyGroup, Subject, AttachmentGroup, AttachmentFile, TaskType
)
from users.permissions import IsAdministration, IsTeacher, IsStudent, IsCurator

User = get_user_model()

def check_lesson_started(lesson):
    # Дозволяємо редагування, якщо поточний час >= часу початку пари
    if timezone.now() < lesson.start_time:
        raise ValidationError("Ви не можете редагувати дані пари, яка ще не почалася.")

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
            students = Student.objects.filter(study_group=task.study_group)

            end_date = task.end
            if isinstance(end_date, str):
                # Перетворюємо рядок "2026-03-30" (стандарт з HTML-інпута) на "30.03.2026"
                # Якщо формат відрізняється, беремо просто перші 10 символів
                try:
                    formatted_deadline = datetime.strptime(end_date[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
                except ValueError:
                    formatted_deadline = end_date # Фолбек, якщо щось піде не так
            else:
                formatted_deadline = end_date.strftime('%d.%m.%Y')
            
            # Відправляємо кожному
            for student in students:
                TaskStatus.objects.create(
                    task=task,
                    student=student,
                    status=0 # 0 = 'Нове/Не виконано'
                )
                try:
                    create_and_send_notification(
                        recipient=student.person.user,
                        title=f"Нове завдання: {task.subject.name}",
                        message=f"Викладач додав нове завдання з теми: {task.theme}.",
                        category='education',
                        related_id=str(task.id)
                    )
                except Exception as e:
                    print(f"Помилка відправки сповіщення: {e}")
            
            return Response({"id": task.id}, status=status.HTTP_201_CREATED)
        
class TeacherGroupsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]
    
    def get(self, request):
        # Отримуємо всі унікальні групи, в яких у цього юзера є хоча б одна пара
        groups = StudyGroup.objects.filter(
            lessons__teacher=request.user
        ).distinct()
        
        data = [{"id": str(g.id), "name": g.name} for g in groups]
        return Response(data)

class TasksTypeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        task_types = TaskType.objects.all()
        data = [{"id": str(t.id), "name": t.name} for t in task_types]
        return Response(data, status=status.HTTP_200_OK)

class TeacherSubjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_id = request.query_params.get('group_id')
        user = request.user

        # Якщо адмін — бачить все
        if user.groups.filter(name='administration').exists():
            subjects = Subject.objects.all()
        # Якщо вчитель і вибрана група — бачить тільки свої предмети в цій групі
        elif group_id:
            subjects = Subject.objects.filter(
                lesson__teacher=user,
                lesson__study_group_id=group_id
            ).distinct()
        # В іншому випадку — просто всі предмети, де він вказаний як викладач
        else:
            subjects = Subject.objects.filter(lesson__teacher=user).distinct()

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
            TaskChecked.objects.create(
                task=submission.task,
                student=submission.student,
                mark=mark,
                comment=comment
            )
            
            TaskStatus.objects.filter(
                task=submission.task, 
                student=submission.student
            ).update(status=2)
            
            # 🔥 Зберігаємо дані для сповіщення ПЕРЕД тим, як видалити submission
            student_user = submission.student.person.user
            task_theme = submission.task.theme
            task_id = submission.task.id
            
            # Видаляємо з черги на перевірку
            submission.delete()
            
            # 🔥 ВІДПРАВЛЯЄМО СПОВІЩЕННЯ СТУДЕНТУ 🔥
            try:
                create_and_send_notification(
                    recipient=student_user,
                    title="Роботу оцінено!",
                    message=f"Викладач виставив {mark} балів за завдання '{task_theme}'.",
                    category='education',
                    related_id=str(task_id)
                )
            except Exception as e:
                print(f"Помилка відправки сповіщення: {e}")
            
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
            student = get_object_or_404(Student, person__user=request.user)
            task_id = request.data.get('task_id')
            
            # 🔥 Дістаємо саме завдання, щоб знати, кому відправляти сповіщення (автору)
            task = get_object_or_404(Task, id=task_id)
            
            files = request.FILES.getlist('file') or request.FILES.getlist('attachments')
            
            att_group = None
            if files:
                att_group = AttachmentGroup.objects.create()
                for f in files:
                    AttachmentFile.objects.create(group=att_group, file=f)

            TaskOnCheck.objects.create(
                task_id=task_id,
                student=student,
                text=request.data.get('text', ''),
                attachments=att_group  
            )

            TaskStatus.objects.filter(
                task_id=task_id, 
                student=student
            ).update(status=1)

            # 🔥 ВІДПРАВЛЯЄМО СПОВІЩЕННЯ ВЧИТЕЛЮ 🔥
            try:
                student_name = f"{student.person.name} {student.person.surname}"
                create_and_send_notification(
                    recipient=task.author, # Автор завдання - це наш вчитель
                    title="Нова робота на перевірку!",
                    message=f"Студент {student_name} здав роботу з теми '{task.theme}'.",
                    category='education',
                    related_id=str(task.id)
                )
            except Exception as e:
                print(f"Помилка відправки сповіщення: {e}")

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

        try:
            create_and_send_notification(
                recipient=lesson.teacher,
                title="Оновлення розкладу",
                message=f"Вам призначено нову пару: {lesson.subject.name}",
                category='education',
                related_id=str(lesson.id)
            )
        except Exception as e:
            print(f"Помилка сокета вчителя: {e}")

        # 🔥 2. СПОВІЩАЄМО СТУДЕНТІВ (щоб їхні календарі оновилися миттєво) 🔥
        students = Student.objects.filter(study_group_id=group_id).select_related('person__user')
        for student in students:
            try:
                create_and_send_notification(
                    recipient=student.person.user,
                    title="Зміни в розкладі!",
                    message=f"Додано нову пару: {lesson.subject.name}",
                    category='education',
                    related_id=str(lesson.id)
                )
            except Exception as e:
                print(f"Помилка сокета студента: {e}")

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
        curators = User.objects.filter(groups__name="curator").select_related('person')
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
    
# Отримання пар вчителя на сьогодні
class TeacherLessonsTodayView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher] # Додали захист

    def get(self, request):
        # 1. Шукаємо параметр date в URL
        date_str = request.query_params.get('date')
        
        if date_str:
            try:
                # Перетворюємо рядок з фронтенду в об'єкт дати
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Неправильний формат дати."}, status=400)
        else:
            # Якщо параметра немає — беремо сьогодні
            target_date = timezone.now().date()

        # 2. Фільтруємо пари за цією датою і сортуємо за часом
        lessons = Lesson.objects.filter(
            teacher=request.user,
            start_time__date=target_date
        ).select_related('study_group', 'subject').order_by('start_time')
        
        data = [{
            "id": str(l.id),
            "study_group_name": l.study_group.name,
            "subject_name": l.subject.name,
            "start_time": l.start_time,
            "end_time": l.end_time,
            "theme": l.theme 
        } for l in lessons]
        
        return Response(data)

# Студенти групи з їхніми статусами по конкретній парі
class LessonStudentsView(APIView):
    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        students = Student.objects.filter(study_group=lesson.study_group).select_related('person')
        
        ducks_map = set(LessonDuck.objects.filter(lesson=lesson).values_list('student_id', flat=True))
        attendance_map = {a.student_id: a.status for a in Attendance.objects.filter(lesson=lesson)}
        
        # Додаємо мапу оцінок
        marks_map = {m.student_id: m.grade for m in LessonMark.objects.filter(lesson=lesson)}
        
        data = []
        for s in students:
            data.append({
                "id": str(s.id),
                "profile_id": str(s.person.user.id),
                "full_name": s.person.get_full_name(),
                "attendance_status": attendance_map.get(s.id, None),
                "duck_active": s.id in ducks_map,
                "grade": marks_map.get(s.id, None) # Віддаємо оцінку
            })
        return Response({"students": data})

# Оновлення теми пари (onBlur)
class UpdateLessonThemeView(APIView):
    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        lesson.theme = request.data.get('theme', '')
        lesson.save()
        return Response({"status": "success"})

# Відвідуваність
class SetAttendanceView(APIView):
    def post(self, request):
        lesson_id = request.data.get('lesson_id')
        student_id = request.data.get('student_id')
        status_val = request.data.get('status')

        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # 🔥 Дістаємо студента, щоб відправити йому сповіщення
        student = get_object_or_404(Student, id=student_id)
        
        # Перевірка часу
        if timezone.now() < lesson.start_time:
            return Response(
                {"error": "badtime"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Перетворюємо статус в число про всяк випадок
        status_int = int(status_val)
        
        attendance, created = Attendance.objects.update_or_create(
            lesson_id=lesson_id, student_id=student_id,
            defaults={'status': status_int}
        )

        # 🔥 ВІДПРАВЛЯЄМО СПОВІЩЕННЯ СТУДЕНТУ ПО СОКЕТУ 🔥
        status_texts = {0: "Відсутній", 1: "Присутній", 2: "Запізнення"}
        text_status = status_texts.get(status_int, "Невідомо")

        try:
            create_and_send_notification(
                recipient=student.person.user,
                title="Відвідуваність",
                message=f"Ваш статус на парі '{lesson.subject.name}': {text_status}",
                category='education',
                related_id=str(lesson.id)
            )
        except Exception as e:
            print(f"Помилка відправки сповіщення про відвідуваність: {e}")

        return Response({"status": "ok"})

# Оцінка за пару + Coins
class GradeLessonStudentView(APIView):
    def post(self, request):
        student_id = request.data.get('student_id')
        lesson_id = request.data.get('lesson_id')
        grade_val = request.data.get('grade')

        if not all([student_id, lesson_id, grade_val]):
            return Response({"error": "Missing data"}, status=status.HTTP_400_BAD_REQUEST)

        lesson = get_object_or_404(Lesson, id=lesson_id)
        student = get_object_or_404(Student, id=student_id)

        if timezone.now() < lesson.start_time:
            return Response({"error": "badtime"}, status=status.HTTP_400_BAD_REQUEST)

        # Створюємо або оновлюємо оцінку
        mark, created = LessonMark.objects.update_or_create(
            lesson=lesson, 
            student=student,
            defaults={'grade': int(grade_val)}
        )

        try:
            create_and_send_notification(
                recipient=student.person.user,
                title="Нова оцінка!",
                message=f"Ви отримали {mark.grade} балів на парі з предмета '{lesson.subject.name}'.",
                category='education',
                related_id=str(lesson.id)
            )
        except Exception as e:
            print(f"Помилка відправки сповіщення: {e}")

        return Response({"status": "success", "grade": mark.grade})

# Заохочення (Ducks)
class ToggleDuckView(APIView):
    # Додаємо аргументи після request
    def post(self, request, lesson_id, student_id): 
        lesson = get_object_or_404(Lesson, id=lesson_id)
        student = get_object_or_404(Student, id=student_id)

        if timezone.now() < lesson.start_time:
            return Response(
                {"error": "badtime"}, 
                status=status.HTTP_400_BAD_REQUEST
            )    
        
        # Шукаємо, чи вже є качка за цю пару цьому студенту
        duck_query = LessonDuck.objects.filter(lesson=lesson, student=student)
        
        if duck_query.exists():
            # Якщо є — забираємо
            duck_query.delete()
            if student.ducks > 0:
                student.ducks -= 1
            active = False
        else:
            # Якщо немає — створюємо
            LessonDuck.objects.create(lesson=lesson, student=student)
            student.ducks += 1
            active = True

            try:
                create_and_send_notification(
                    recipient=student.person.user,
                    title="Качка за активність!",
                    message=f"Викладач дав вам заохочення на парі з '{lesson.subject.name}'.",
                    category='education',
                    related_id=str(lesson.id)
                )
            except Exception as e:
                print(f"Помилка відправки сповіщення: {e}")
            
        student.save()
        
        return Response({
            "active": active, 
            "total_ducks": student.ducks
        }, status=status.HTTP_200_OK)


class StudentDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        student = get_object_or_404(
            Student.objects.select_related('study_group', 'person'), 
            person__user=request.user
        )
        group = student.study_group

        # Рахуємо особисту статистику (оцінки)
        task_sum = TaskChecked.objects.filter(student=student).aggregate(s=Sum('mark'))['s'] or 0
        lesson_sum = LessonMark.objects.filter(student=student).aggregate(s=Sum('grade'))['s'] or 0
        total_coins = task_sum + lesson_sum

        all_marks = list(TaskChecked.objects.filter(student=student).values_list('mark', flat=True)) + \
                    list(LessonMark.objects.filter(student=student).values_list('grade', flat=True))
        avg_grade = sum(all_marks) / len(all_marks) if all_marks else 0.0

        response_data = {
            "group_name": group.name if group else None,
            "my_stats": {
                "ducks": student.ducks,
                "coins": total_coins,
                "average_grade": round(float(avg_grade), 1)
            },
            "leaderboard": []
        }

        if group:
            tasks_sq = TaskChecked.objects.filter(
                student=OuterRef('pk')
            ).values('student').annotate(total=Sum('mark')).values('total')

            lessons_sq = LessonMark.objects.filter(
                student=OuterRef('pk')
            ).values('student').annotate(total=Sum('grade')).values('total')

            group_students = Student.objects.filter(study_group=group).select_related('person__user').annotate(
                task_score=Coalesce(Subquery(tasks_sq), Value(0)),
                lesson_score=Coalesce(Subquery(lessons_sq), Value(0))
            )

            leaderboard = []
            for s in group_students:
                s_total_coins = s.task_score + s.lesson_score
                total_points = s_total_coins + s.ducks # 🔥 СУМУЄМО МОНЕТИ ТА КАЧКИ

                leaderboard.append({
                    "id": str(s.person.user.id), 
                    "full_name": s.person.get_full_name(),
                    "coins": s_total_coins,
                    "ducks": s.ducks,
                    "total_points": total_points # Додаємо нове поле для сортування і фронта
                })

            # 🔥 СОРТУЄМО ЗА ЗАГАЛЬНОЮ СУМОЮ (total_points)
            response_data["leaderboard"] = sorted(leaderboard, key=lambda x: x['total_points'], reverse=True)

        return Response(response_data)

class CalendarLessonsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Отримуємо дату від фронта (наприклад, 2024-05-20), або беремо сьогодні
        date_str = request.query_params.get('date')
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = timezone.now().date()

        # Знаходимо початок тижня (Неділя як у GitHub)
        # weekday() в Python: 0=Пн, ..., 6=Нд. 
        # Якщо сьогодні Нд(6), нам треба відняти 0 днів. Якщо Пн(0) — відняти 1.
        days_to_subtract = (target_date.weekday() + 1) % 7
        start_of_week = target_date - timedelta(days=days_to_subtract)
        end_of_week = start_of_week + timedelta(days=7)

        lessons_query = Lesson.objects.filter(
            start_time__date__gte=start_of_week,
            start_time__date__lt=end_of_week
        ).select_related('subject', 'study_group', 'lesson_type')

        # Фільтрація по ролі (як у тебе було)
        person = getattr(request.user, 'person', None)
        if hasattr(person, 'student') and request.headers.get('X-Active-Role') == 'student':
            lessons_query = lessons_query.filter(study_group=person.student.study_group)
        else:
            lessons_query = lessons_query.filter(teacher=request.user)

        data = []
        for l in lessons_query:
            # 1. Конвертуємо час з UTC у Київський (локальний)
            local_start = timezone.localtime(l.start_time)
            local_end = timezone.localtime(l.end_time)

            # 2. Вирішуємо конфлікт днів тижня між Python та JS
            # У Python: Пн = 0, Нд = 6
            # У JavaScript (на твоєму фронті): Нд = 0, Пн = 1
            js_day = (local_start.weekday() + 1) % 7

            data.append({
                "id": str(l.id),
                "title": l.subject.name,
                "type": l.lesson_type.name if l.lesson_type else "Заняття",
                "start": local_start.strftime("%H:%M"),
                "end": local_end.strftime("%H:%M"),
                "day": js_day, 
                "date": local_start.date().isoformat(),
                "classroom": l.classroom,
                "teacher_id": str(l.teacher.id)
            })
        
        return Response(data)
    
class AdminNewsView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        news_list = News.objects.all().order_by('-created_at')
        data = []
        for n in news_list:
            data.append({
                "id": str(n.id),
                "title": n.title,
                "text": n.text,
                "image": request.build_absolute_uri(n.image.url) if n.image else None,
                "created_at": n.created_at.isoformat(),
            })
        return Response(data)

    def post(self, request):
        title = request.data.get('title')
        text = request.data.get('text')
        image = request.FILES.get('image')

        if not title or not text:
            return Response({"error": "Заголовок і текст обов'язкові."}, status=400)
        
        if len(title) > 200 or len(text) > 4096:
            return Response({"error": "Перевищено ліміт символів."}, status=400)

        news = News.objects.create(title=title, text=text, image=image)

        # 🔥 ВІДПРАВЛЯЄМО СПОВІЩЕННЯ ВСІМ СТУДЕНТАМ 🔥
        students = Student.objects.select_related('person__user').all()
        for student in students:
            if hasattr(student, 'person') and hasattr(student.person, 'user'):
                try:
                    create_and_send_notification(
                        recipient=student.person.user,
                        title="Нова новина!",
                        message=news.title,
                        category='education', 
                        related_id=str(news.id)
                    )
                except Exception as e:
                    print(f"Помилка відправки сповіщення: {e}")

        return Response({"status": "created", "id": str(news.id)}, status=201)
    
class AdminNewsDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]
    parser_classes = (MultiPartParser, FormParser)

    def patch(self, request, news_id):
        news = get_object_or_404(News, id=news_id)
        
        title = request.data.get('title')
        text = request.data.get('text')
        image = request.FILES.get('image')

        if title:
            if len(title) > 200: return Response({"error": "Перевищено ліміт"}, status=400)
            news.title = title
            
        if text:
            if len(text) > 4096: return Response({"error": "Перевищено ліміт"}, status=400)
            news.text = text
            
        if image:
            news.image = image

        news.save()
        return Response({"status": "updated"})

    def delete(self, request, news_id):
        news = get_object_or_404(News, id=news_id)
        news.delete()
        return Response({"status": "deleted"})

class StudentNewsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        student = getattr(request.user.person, 'student', None)
        if not student:
            return Response({"error": "Студента не знайдено"}, status=400)

        read_subquery = NewsReadStatus.objects.filter(
            news=OuterRef('pk'), 
            student=student
        )

        news_list = News.objects.annotate(
            is_read=Exists(read_subquery)
        ).order_by('-created_at')

        data = []
        for n in news_list:
            data.append({
                "id": str(n.id),
                "title": n.title,
                "text": n.text,
                "image": request.build_absolute_uri(n.image.url) if n.image else None,
                "created_at": n.created_at.isoformat(),
                "is_read": n.is_read
            })
        return Response(data)

class MarkNewsReadView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, news_id):
        student = getattr(request.user.person, 'student', None)
        if not student:
            return Response({"error": "Студента не знайдено"}, status=400)

        news = get_object_or_404(News, id=news_id)
        
        NewsReadStatus.objects.get_or_create(news=news, student=student)
        
        return Response({"status": "read"})
    
class StudentAttendanceHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        student = request.user.person.student
        attendances = Attendance.objects.filter(student=student).select_related('lesson__subject').order_by('-lesson__start_time')[:80]
        data = [{
            "id": str(a.id),
            "subject_name": a.lesson.subject.name,
            "date": a.lesson.start_time.isoformat(),
            "status": a.status
        } for a in reversed(attendances)]
        
        return Response(data)
    
class AdminSubjectView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def get(self, request):
        subjects = Subject.objects.all().order_by('name')
        data = [{"id": str(s.id), "name": s.name} for s in subjects]
        return Response(data)

    def post(self, request):
        name = request.data.get('name')
        if not name:
            return Response({"error": "Назва обов'язкова"}, status=400)
        Subject.objects.create(name=name)
        return Response({"status": "created"}, status=201)

    def patch(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        if 'name' in request.data:
            subject.name = request.data['name']
            subject.save()
        return Response({"status": "updated"})

    def delete(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        subject.delete()
        return Response({"status": "deleted"})
    
class AdminTaskTypeView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def get(self, request):
        types = TaskType.objects.all().order_by('name')
        data = [{"id": str(t.id), "name": t.name} for t in types]
        return Response(data)

    def post(self, request):
        name = request.data.get('name')
        if not name:
            return Response({"error": "Назва обов'язкова"}, status=400)
        TaskType.objects.create(name=name)
        return Response({"status": "created"}, status=201)

    def patch(self, request, pk):
        task_type = get_object_or_404(TaskType, pk=pk)
        if 'name' in request.data:
            task_type.name = request.data['name']
            task_type.save()
        return Response({"status": "updated"})

    def delete(self, request, pk):
        task_type = get_object_or_404(TaskType, pk=pk)
        task_type.delete()
        return Response({"status": "deleted"})
    
class AdminLessonTypeView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def get(self, request):
        types = LessonType.objects.all().order_by('name')
        data = [{"id": str(t.id), "name": t.name} for t in types]
        return Response(data)

    def post(self, request):
        name = request.data.get('name')
        if not name:
            return Response({"error": "Назва обов'язкова"}, status=400)
        LessonType.objects.create(name=name)
        return Response({"status": "created"}, status=201)

    def patch(self, request, pk):
        task_type = get_object_or_404(LessonType, pk=pk)
        if 'name' in request.data:
            task_type.name = request.data['name']
            task_type.save()
        return Response({"status": "updated"})

    def delete(self, request, pk):
        task_type = get_object_or_404(LessonType, pk=pk)
        task_type.delete()
        return Response({"status": "deleted"})