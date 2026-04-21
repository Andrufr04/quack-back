from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from education.models import Student
from users.permissions import IsAdministration
from .serializers import MyTokenObtainPairSerializer
from django.db import transaction
from django.utils import timezone
import random
from datetime import timedelta
from .models import User
from profiles.models import Person, Profile
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.conf import settings

def get_email_template(code, theme='light', title="Відновлення паролю", desc="Ви зробили запит на відновлення паролю."):
    if theme == 'dark':
        bg_color, card_bg, text_color, border_color, muted_text, code_bg = "#121212", "#1e1e1e", "#e0e0e0", "#333333", "#a0a0a0", "#2a2a2a"
    else:
        bg_color, card_bg, text_color, border_color, muted_text, code_bg = "#f4f7f6", "#ffffff", "#333333", "#eaeaea", "#777777", "#f9f9f9"
        
    return f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: {bg_color}; padding: 40px 20px;">
        <div style="max-width: 500px; margin: 0 auto; background-color: {card_bg}; border: 1px solid {border_color}; border-radius: 16px; padding: 40px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
            <h2 style="color: #ec8735; text-align: center; margin-top: 0; font-size: 28px; letter-spacing: 1px;">Quack</h2>
            <p style="font-size: 16px; line-height: 1.5; color: {text_color};">Вітаємо!</p>
            <p style="font-size: 16px; line-height: 1.5; color: {text_color};">{desc}</p>
            <p style="font-size: 16px; line-height: 1.5; color: {text_color};">Ваш код підтвердження:</p>
            
            <div style="background-color: {code_bg}; border: 1px solid {border_color}; border-radius: 12px; padding: 20px; text-align: center; margin: 30px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #ec8735;">{code}</span>
            </div>
            
            <p style="font-size: 14px; color: {muted_text}; text-align: center;">Код дійсний протягом <strong>15 хвилин</strong>.</p>
            <hr style="border: 0; border-top: 1px solid {border_color}; margin: 30px 0;" />
            <p style="font-size: 12px; color: {muted_text}; text-align: center; margin-bottom: 0; line-height: 1.5;">
                Якщо ви не робили цей запит, просто проігноруйте це повідомлення.
            </p>
        </div>
    </div>
    """

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class AdminCreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def post(self, request):
        data = request.data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=data['email'],
                    password="123456"
                )
                
                person = Person.objects.create(
                    user=user,
                    name=data['name'],
                    surname=data['surname'],
                    patronymic=data.get('patronymic'),
                    birthdate=data['birthdate']
                )
                
                Profile.objects.create(person=person)
                
                return Response({"detail": "Користувача створено успішно"}, status=201)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        
class AdminManageUsersView(APIView):
    permission_classes = [IsAuthenticated, IsAdministration]

    def get(self, request):
        ordering = request.query_params.get('ordering', 'email')
        users = User.objects.select_related('person', 'person__student__study_group').prefetch_related('groups')
        data = []
        for u in users:
            person = getattr(u, 'person', None)
            student = getattr(person, 'student', None) if person else None

            data.append({
                "id": str(u.id),
                "email": u.email,
                "full_name": person.get_full_name() if person else "Admin",
                "is_active": u.is_active,
                "is_deleted": u.deleted_at is not None,
                "roles": [g.name for g in u.groups.all()],
                "group": {
                    "id": str(student.study_group.id),
                    "name": student.study_group.name
                } if student and student.study_group else None
            })
        return Response(data)

    def patch(self, request, pk):
        user = User.objects.get(pk=pk)
        data = request.data
        action = data.get('action')

        with transaction.atomic():
            if action == 'toggle_active':
                user.is_active = not user.is_active
                user.deleted_at = timezone.now() if not user.is_active else None
            
            if 'roles' in data:
                roles = data['roles']
                groups = Group.objects.filter(name__in=roles)
                user.groups.set(groups)
                
                # Якщо додали роль student, але об'єкта Student ще немає — створюємо
                if 'student' in roles and hasattr(user, 'person'):
                    Student.objects.get_or_create(person=user.person)

            # Оновлення групи (тільки для тих, у кого є запис Student)
            if 'study_group' in data:
                group_id = data.get('study_group')
                if hasattr(user, 'person') and hasattr(user.person, 'student'):
                    student = user.person.student
                    student.study_group_id = group_id if group_id else None
                    student.save()
            
            user.save()
            
        return Response({"status": "updated"})

# У файлі users/views.py знайди SwitchRoleView і онови метод post:

class SwitchRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_role = request.data.get('role')
        user = request.user
        
        user_groups = user.groups.values_list('name', flat=True)
        if new_role not in user_groups:
            return Response({"detail": "no access"}, status=403)

        refresh = RefreshToken.for_user(user)
        refresh['active_role'] = new_role
        refresh['roles'] = list(user_groups)
        
        group_id = None
        if hasattr(user, 'person') and hasattr(user.person, 'student'):
            student = user.person.student
            if student.study_group:
                group_id = str(student.study_group.id)
                
        refresh['group_id'] = group_id

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'active_role': new_role
        })
    
class PasswordResetRequestView(APIView):
    # Доступно всім, без авторизації
    permission_classes = [] 

    def post(self, request):
        email = request.data.get('email')
        theme = request.data.get('theme', 'light')
        user = User.objects.filter(email=email).first()
        
        if not user:
            return Response({"status": "ok"})

        # 🔥 Генеруємо 6-значний код (може починатися з нулів, наприклад 012021)
        code = f"{random.randint(0, 999999):06d}"
        
        user.email_code = code
        user.email_code_iat = timezone.now()
        user.save()

        # 🔥 КРАСИВИЙ HTML-ШАБЛОН ЛИСТА В СТИЛІ QUACK 🔥
        html_content = get_email_template(code, theme=theme)

        # Відправляємо лист
        send_mail(
            subject='Quack: Відновлення паролю',
            message=f'Ваш код для відновлення паролю: {code}', # Це побачать юзери зі старими поштовиками без HTML
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            html_message=html_content # 🔥 Додаємо HTML версію
        )
        return Response({"status": "ok"})


class PasswordResetConfirmView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        new_password = request.data.get('new_password')

        user = User.objects.filter(email=email).first()
        
        if not user or user.email_code != code:
            return Response({"error": "Невірний код"}, status=400)

        if timezone.now() > user.email_code_iat + timedelta(minutes=15):
            return Response({"error": "Час дії коду вичерпано"}, status=400)

        # 🔥 ПЕРЕВІРКА: Новий пароль не повинен співпадати зі старим 🔥
        if user.check_password(new_password):
            return Response({"error": "Новий пароль не може бути таким самим як попередній!"}, status=400)

        user.set_password(new_password)
        user.email_code = None
        user.last_password_change = timezone.now()
        user.save()
        
        return Response({"status": "ok"})
    
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        # 1. Перевіряємо чи правильний старий пароль
        if not user.check_password(old_password):
            return Response({"error": "Невірний поточний пароль"}, status=400)
        
        # 2. Перевіряємо чи не однаковий новий пароль зі старим
        if old_password == new_password:
            return Response({"error": "Новий пароль повинен відрізнятись від старого"}, status=400)
        
        # 3. Якщо все ок - зберігаємо
        user.set_password(new_password)
        user.last_password_change = timezone.now()
        user.save()

        return Response({"status": "ok"})
    
class EmailChangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_email = request.data.get('new_email')
        theme = request.data.get('theme', 'light')

        if not new_email:
            return Response({"error": "Введіть нову пошту"}, status=400)
        if User.objects.filter(email=new_email).exists():
            return Response({"error": "Ця пошта вже використовується іншим користувачем!"}, status=400)

        code = f"{random.randint(0, 999999):06d}"
        user.email_code = code
        user.email_code_iat = timezone.now()
        user.save()

        html_content = get_email_template(
            code, theme=theme, 
            title="Зміна пошти", 
            desc="Ви зробили запит на зміну електронної пошти для вашого облікового запису."
        )

        send_mail(
            subject='Quack: Підтвердження нової пошти',
            message=f'Ваш код підтвердження: {code}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[new_email], # Відправляємо на НОВУ пошту
            fail_silently=False,
            html_message=html_content
        )
        return Response({"status": "ok"})

class EmailChangeConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_email = request.data.get('new_email')
        code = request.data.get('code')

        if not user.email_code or user.email_code != code:
            return Response({"error": "Невірний код"}, status=400)

        if timezone.now() > user.email_code_iat + timedelta(minutes=15):
            return Response({"error": "Час дії коду вичерпано"}, status=400)

        if User.objects.filter(email=new_email).exists():
            return Response({"error": "Ця пошта вже зайнята"}, status=400)

        user.email = new_email
        user.email_code = None
        user.save()
        
        return Response({"status": "ok"})