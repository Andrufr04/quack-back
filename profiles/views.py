from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Profile, Person
import traceback # Для детального логу помилок

class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        try:
            # Перевіряємо чи є Person у юзера
            person = getattr(request.user, 'person', None)
            if not person:
                return Response({"error": "Person record not found for this user"}, status=404)

            profile = person.profile_set.first()
            if not profile:
                return Response({"error": "No profiles found for this person"}, status=404)
            
            # Отримуємо URL картинки безпечно
            pic_url = None
            if profile.profile_picture:
                try:
                    pic_url = profile.profile_picture.url
                except ValueError: # Якщо файл фізично видалений, але запис є
                    pic_url = None

            return Response({
                "name": f"{person.name} {person.surname}",
                "description": profile.description or "Опис відсутній",
                "profile_picture": pic_url
            })
        except Exception as e:
            print(f"GET ERROR: {e}")
            traceback.print_exc() # Виведе помилку в консоль сервера
            return Response({"error": str(e)}, status=500)

    def patch(self, request):
        try:
            file_obj = request.data.get('profile_picture')
            if not file_obj:
                return Response({"error": "Файл не надано"}, status=400)
                
            person = request.user.person
            profile = person.profile_set.first()

            if not profile:
                return Response({"error": "Profile not found to update"}, status=404)

            # ЗБЕРІГАЄМО САМ ОБ'ЄКТ ФАЙЛУ
            profile.profile_picture = file_obj 
            profile.save()
            
            # Будуємо повний шлях для фронта
            request_uri = request.build_absolute_uri(profile.profile_picture.url)
            
            return Response({
                "message": "Картинку оновлено", 
                "profile_picture": request_uri
            })
        except Exception as e:
            print(f"PATCH ERROR: {e}")
            traceback.print_exc() # Це покаже в консолі Waitress, де саме "впав" код
            return Response({"error": str(e)}, status=500)