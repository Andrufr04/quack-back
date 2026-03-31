from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from notifications.services import create_and_send_notification
from profiles.models import Person, Post, PostImage, Reaction
from users.permissions import IsTeacher
from rest_framework.generics import get_object_or_404
from django.contrib.auth import get_user_model
import traceback
import uuid
import os

User = get_user_model()

class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    # Логіка: (Студент АБО Вчитель) ТА (НЕ Адміністрація)
    # Примітка: ~IsAdministration() працює як заперечення
    # return [IsAuthenticated(), (IsStudent() | IsTeacher()), ~IsAdministration()]

    def get_permissions(self):
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

            banner_url = None
            if profile.banner_picture:
                try:
                    banner_url = request.build_absolute_uri(profile.banner_picture.url)
                except ValueError:
                    banner_url = None

            return Response({
                "id": str(request.user.id),
                "name": f"{person.name} {person.surname}",
                "description": profile.description or "Опис відсутній",
                "profile_picture": pic_url,
                "banner_picture": banner_url
            })
        
        except Exception as e:
            print(f"GET ERROR: {e}")
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)

    def patch(self, request):
        try:
            person = request.user.person
            profile = person.profile_set.first()

            if not profile:
                return Response({"error": "Профіль не знайдено"}, status=404)

            # Оновлюємо опис, якщо він є в запиті
            if 'description' in request.data:
                profile.description = request.data.get('description')

            limit = 5 * 1024 * 1024  # 5 MB
            bannerlimit = 10 * 1024 * 1024  # 10 MB

            # Обробляємо аватарку
            avatar_obj = request.FILES.get('profile_picture')
            if avatar_obj:
                if not avatar_obj.content_type.startswith('image/'):
                    return Response({"error": "Аватар: тільки зображення"}, status=400)
                if avatar_obj.size > limit:
                    return Response({"error": "Аватар занадто великий"}, status=400)
                
                ext = os.path.splitext(avatar_obj.name)[1]
                avatar_obj.name = f"{uuid.uuid4().hex}{ext}"
                profile.profile_picture = avatar_obj 

            # Обробляємо банер
            banner_obj = request.FILES.get('banner_picture')
            if banner_obj:
                if not banner_obj.content_type.startswith('image/'):
                    return Response({"error": "Банер: тільки зображення"}, status=400)
                if banner_obj.size > bannerlimit:
                    return Response({"error": "Банер занадто великий"}, status=400)
                
                ext = os.path.splitext(banner_obj.name)[1]
                banner_obj.name = f"{uuid.uuid4().hex}{ext}"
                profile.banner_picture = banner_obj 

            profile.save()
            
            # Повертаємо оновлені URL
            return Response({
                "message": "Профіль оновлено", 
                "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                "banner_picture": request.build_absolute_uri(profile.banner_picture.url) if profile.banner_picture else None
            })

        except Exception as e:
            print(f"PATCH ERROR: {e}")
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # 1. Шукаємо Person саме за user_id (це те, що в таблиці profiles_person.user_id)
        # Використовуємо filter().first(), щоб уникнути помилок, якщо запису немає
        person = get_object_or_404(Person, user_id=user_id)
        
        # 2. Отримуємо профіль через зворотний зв'язок від Person
        # Оскільки у тебе Profile має ForeignKey на Person:
        profile = person.profile_set.first()

        if not profile:
            # Якщо Person є, а Profile ще не створили — 
            # повернемо 404 або створимо порожній "на льоту"
            return Response({"error": "Профіль для цього користувача ще не налаштований"}, status=404)

        pic_url = request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None
        banner_url = request.build_absolute_uri(profile.banner_picture.url) if profile.banner_picture else None

        return Response({
            "id": str(user_id), # Повертаємо той самий ID користувача
            "name": f"{person.name} {person.surname}",
            "description": profile.description or "Опис відсутній",
            "profile_picture": pic_url,
            "banner_picture": banner_url
        })
    
class PostListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser) # Важливо для прийому файлів

    def get(self, request, user_id):
        posts = Post.objects.filter(author_id=user_id).order_by('-created_at')
        data = []
        for post in posts:
            reactions_count = {}
            for emoji, _ in Reaction.EMOJI_CHOICES:
                reactions_count[emoji] = post.reactions.filter(emoji=emoji).count()
            
            user_reaction = post.reactions.filter(user=request.user).first()

            # 🔥 Збираємо всі картинки цього поста у список
            images = [request.build_absolute_uri(img.image.url) for img in post.images.all()]

            data.append({
                "id": post.id,
                "title": post.title,
                "text": post.text,
                "images": images, # 🔥 Тепер це масив (images замість image)
                "created_at": post.created_at,
                "reactions": reactions_count,
                "my_reaction": user_reaction.emoji if user_reaction else None
            })
        return Response(data)

    def post(self, request):
        title = request.data.get('title')
        text = request.data.get('text', '')
        images_data = request.FILES.getlist('image')

        if not title and not text and not images_data:
            return Response({"error": "Пост не може бути порожнім"}, status=400)
        
        # 🔥 ВАЛІДАЦІЯ ТЕКСТУ 🔥
        if len(text) > 4096:
            return Response({"error": "Текст поста не може перевищувати 4096 символів."}, status=400)
        
        # Рахуємо кількість переносів рядка (\n)
        if text.count('\n') > 100:
            return Response({"error": "Забагато переносів на новий рядок (максимум 100)."}, status=400)

        # 🔥 ВАЛІДАЦІЯ ФАЙЛІВ 🔥
        limit = 10 * 1024 * 1024  
        
        for img in images_data[:5]: 
            if not img.content_type.startswith('image/'):
                return Response({"error": f"Файл {img.name} не є зображенням. Відео та інші формати заборонені!"}, status=400)
            
            if img.size > limit:
                return Response({"error": f"Файл {img.name} занадто великий (макс. 10 МБ)"}, status=400)

        # 1. Створюємо сам пост (тільки якщо всі картинки пройшли перевірку)
        post = Post.objects.create(
            author=request.user,
            title=title,
            text=text
        )

        # 2. Зберігаємо картинки
        for img in images_data[:5]:
            PostImage.objects.create(post=post, image=img)

        return Response({"status": "created", "id": post.id}, status=201)

class ReactionToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        emoji = request.data.get('emoji')
        post = get_object_or_404(Post, id=post_id)
        user = request.user
        
        existing_reaction = Reaction.objects.filter(post=post, user=user).first()

        if existing_reaction:
            if existing_reaction.emoji == emoji:
                existing_reaction.delete()
                return Response({"status": "removed"})
            else:
                existing_reaction.emoji = emoji
                existing_reaction.save()
                # Можна додати сповіщення і тут, але зазвичай 
                # при заміні емодзі нове сповіщення не шлють.
                return Response({"status": "updated"})
        
        # Створюємо нову реакцію
        Reaction.objects.create(post=post, user=user, emoji=emoji)

        # 🔥 ВІДПРАВЛЯЄМО СПОВІЩЕННЯ АВТОРУ ПОСТА 🔥
        # Перевіряємо, щоб не надсилати сповіщення самому собі
        if post.author != user:
            try:
                # Формуємо ім'я того, хто поставив реакцію
                sender_name = f"{user.person.name} {user.person.surname}"
                
                create_and_send_notification(
                    recipient=post.author,
                    title="Нова реакція!",
                    message=f"{sender_name} відреагував {emoji} на ваш пост.",
                    category='social', # 🔥 Категорія Соціальне!
                    related_id=str(post.id)
                )
            except Exception as e:
                print(f"Notification error: {e}")

        return Response({"status": "added"})