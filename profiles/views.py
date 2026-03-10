from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from users.permissions import IsTeacher
import traceback

class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    # Логіка: (Студент АБО Вчитель) ТА (НЕ Адміністрація)
    # Примітка: ~IsAdministration() працює як заперечення
    # return [IsAuthenticated(), (IsStudent() | IsTeacher()), ~IsAdministration()]

    def get_permissions(self):
        if self.request.method == 'PATCH':
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated()]

    def get(self, request):
        try:
            person = getattr(request.user, 'person', None)
            if not person:
                return Response({"error": "Person record not found for this user"}, status=404)

            profile = person.profile_set.first()
            if not profile:
                return Response({"error": "No profiles found for this person"}, status=404)
            
            pic_url = None
            if profile.profile_picture:
                try:
                    pic_url = profile.profile_picture.url
                except ValueError:
                    pic_url = None

            return Response({
                "name": f"{person.name} {person.surname}",
                "description": profile.description or "Опис відсутній",
                "profile_picture": pic_url
            })
        except Exception as e:
            print(f"GET ERROR: {e}")
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)

    def patch(self, request):
        try:
            file_obj = request.data.get('profile_picture')
            if not file_obj:
                return Response({"error": "Файл не надано"}, status=400)

            if not file_obj.content_type.startswith('image/'):
                return Response({"error": "Дозволено завантажувати тільки зображення"}, status=400)
            
            limit = 5 * 1024 * 1024  # 5 MB
            if file_obj.size > limit:
                return Response({"error": "Файл занадто великий (макс. 5МБ)"}, status=400)
                
            person = request.user.person
            profile = person.profile_set.first()

            if not profile:
                return Response({"error": "Профіль не знайдено"}, status=404)

            profile.profile_picture = file_obj 
            profile.save()
            
            request_uri = request.build_absolute_uri(profile.profile_picture.url)
            
            return Response({
                "message": "Картинку оновлено", 
                "profile_picture": request_uri
            })
        except Exception as e:
            print(f"PATCH ERROR: {e}")
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)