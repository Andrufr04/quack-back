from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from users.permissions import IsAdministration
from .serializers import MyTokenObtainPairSerializer
from django.db import transaction
from django.utils import timezone
from .models import User
from profiles.models import Person, Profile
from django.contrib.auth.models import Group

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
        users = User.objects.select_related('person').prefetch_related('groups')
        data = []
        for u in users:
            person = getattr(u, 'person', None)
            data.append({
                "id": str(u.id),
                "email": u.email,
                "full_name": person.get_full_name() if person else "Admin",
                "is_active": u.is_active,
                "is_deleted": u.deleted_at is not None,
                "roles": [g.name for g in u.groups.all()]
            })
        return Response(data)

    def patch(self, request, pk):
        user = User.objects.get(pk=pk)
        action = request.data.get('action')

        if action == 'toggle_active':
            user.is_active = not user.is_active
            user.deleted_at = timezone.now() if not user.is_active else None
        
        if 'roles' in request.data:
            groups = Group.objects.filter(name__in=request.data['roles'])
            user.groups.set(groups)
            
        user.save()
        return Response({"status": "updated"})

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

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'active_role': new_role
        })

