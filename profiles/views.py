from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from notifications.services import create_and_send_notification
from profiles.models import Chat, Comment, Message, MessageImage, Person, Post, PostImage, Reaction
from users.permissions import IsTeacher
from rest_framework.generics import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Count
import traceback
import uuid
import os
from rest_framework.exceptions import PermissionDenied
from PIL import Image

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

            images = [request.build_absolute_uri(img.image.url) for img in post.images.all()]

            data.append({
                "id": post.id,
                "title": post.title,
                "text": post.text,
                "images": images, # 🔥 Тепер це масив (images замість image)
                "created_at": post.created_at,
                "reactions": reactions_count,
                "my_reaction": user_reaction.emoji if user_reaction else None,
                "comments_count": post.comments.count() # 🔥 ДОДАЛИ КІЛЬКІСТЬ КОМЕНТАРІВ
            })
        return Response(data)

    def post(self, request):
        title = request.data.get('title')
        text = request.data.get('text', '')
        images_data = request.FILES.getlist('image')

        is_text_empty = not text.strip()
        is_title_empty = not title or not title.strip()

        if is_title_empty and is_text_empty and not images_data:
            return Response({"error": "Пост не може бути порожнім"}, status=400)
        
        # 🔥 ВАЛІДАЦІЯ ТЕКСТУ 🔥
        if len(text) > 4096:
            return Response({"error": "Текст поста не може перевищувати 4096 символів."}, status=400)
        
        # Рахуємо кількість переносів рядка (\n)
        if text.count('\n') > 100:
            return Response({"error": "Забагато переносів на новий рядок (максимум 100)."}, status=400)

        # 🔥 ВАЛІДАЦІЯ ФАЙЛІВ 🔥
        limit = 10 * 1024 * 1024  
        max_resolution = 4096
        
        for img in images_data[:5]: 
            if not img.content_type.startswith('image/'):
                return Response({"error": f"Файл {img.name} не є зображенням. Відео та інші формати заборонені!"}, status=400)
            
            if img.size > limit:
                return Response({"error": f"Файл {img.name} занадто великий (макс. 10 МБ)"}, status=400)
            
            try:
                with Image.open(img) as image_obj:
                    width, height = image_obj.size
                    if width > max_resolution or height > max_resolution:
                        return Response({
                            "error": f"Зображення {img.name} має розмір {width}x{height}. Максимальний дозволений розмір: 4096x4096 пікселів."
                        }, status=400)
            except Exception:
                return Response({"error": f"Файл {img.name} пошкоджений або не є дійсним зображенням."}, status=400)
            finally:
                img.seek(0)

        # 1. Створюємо сам пост (тільки якщо всі картинки пройшли перевірку)
        post = Post.objects.create(
            author=request.user,
            title=title,
            text=text.strip()
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
    
class PostDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        
        if post.author != request.user:
            raise PermissionDenied("Ви не можете видалити чужий пост.")
            
        post.delete()
        return Response({"status": "deleted"}, status=200)
    
class CommentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        # Витягуємо всі коментарі до поста одним запитом
        comments = post.comments.select_related('author__person').all()
        
        data = []
        for c in comments:
            profile = c.author.person.profile_set.first()
            avatar = request.build_absolute_uri(profile.profile_picture.url) if profile and profile.profile_picture else None
            
            data.append({
                'id': str(c.id),
                'parent_id': str(c.parent.id) if c.parent else None,
                'text': c.text,
                'author_id': str(c.author.id),
                'author_name': c.author.person.get_full_name() if hasattr(c.author, 'person') else "Unknown",
                'author_avatar': avatar,
                "author_profile_id": str(c.author.person.user.id),
                'created_at': c.created_at.isoformat()
            })
        return Response(data)

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        text = request.data.get('text', '').strip()
        parent_id = request.data.get('parent_id')

        # 🔥 ВАЛІДАЦІЯ 🔥
        if not text:
            return Response({"error": "Коментар не може бути порожнім"}, status=400)
        if len(text) > 512:
            return Response({"error": "Коментар не може перевищувати 512 символів"}, status=400)
        if text.count('\n') > 8:
            return Response({"error": "Забагато переносів на новий рядок (максимум 8)"}, status=400)

        parent = None
        if parent_id:
            parent = get_object_or_404(Comment, id=parent_id, post=post)

        comment = Comment.objects.create(
            post=post,
            author=request.user,
            parent=parent,
            text=text
        )

        # 🔥 СПОВІЩЕННЯ 🔥
        # 1. Автору поста (якщо це не він сам коментує)
        if post.author != request.user:
            try:
                create_and_send_notification(
                    recipient=post.author, title="Новий коментар",
                    message=f"{request.user.person.get_full_name()} прокоментував ваш пост.",
                    category='social', related_id=str(post.id)
                )
            except Exception: pass

        # 2. Автору коментаря, на який відповідають (якщо це відповідь)
        if parent and parent.author != request.user and parent.author != post.author:
            try:
                create_and_send_notification(
                    recipient=parent.author, title="Відповідь на коментар",
                    message=f"{request.user.person.get_full_name()} відповів на ваш коментар.",
                    category='social', related_id=f"{post.id}:{post.author.id}"
                )
            except Exception: pass

        return Response({"status": "created"}, status=201)

class CommentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        
        # 🔥 ПЕРЕВІРКА ПРАВ: власник коментаря АБО власник поста
        if comment.author != request.user and comment.post.author != request.user:
            raise PermissionDenied("Ви не можете видалити цей коментар.")
            
        comment.delete()
        return Response({"status": "deleted"}, status=200)
    
class ChatListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        chats = Chat.objects.filter(participants=request.user).prefetch_related('participants__person')
        
        data = []
        for chat in chats:
            other_user = chat.participants.exclude(id=request.user.id).first()
            if not other_user:
                continue
                
            profile = other_user.person.profile_set.first()
            avatar = request.build_absolute_uri(profile.profile_picture.url) if profile and profile.profile_picture else None
            
            last_message = chat.messages.last()
            
            # 🔥 РАХУЄМО НЕПРОЧИТАНІ ПОВІДОМЛЕННЯ (від співрозмовника) 🔥
            unread_count = chat.messages.filter(is_read=False).exclude(sender=request.user).count()
            
            data.append({
                "id": str(chat.id),
                "other_user_id": str(other_user.id),
                "name": other_user.person.get_full_name(),
                "avatar": avatar,
                "last_message": last_message.text if last_message else "Немає повідомлень",
                "updated_at": chat.updated_at.isoformat(),
                "unread_count": unread_count # <-- Передаємо на фронт
            })
            
        # Сортуємо: чати з останніми повідомленнями зверху
        data.sort(key=lambda x: x['updated_at'], reverse=True)
        return Response(data)

class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, participants=request.user)

        # Отримуємо зсув для підвантаження історії (скрол вгору)
        offset = int(request.query_params.get('offset', 0))

        # 1. Знаходимо непрочитані повідомлення від співрозмовника
        unread_msgs = chat.messages.filter(is_read=False).exclude(sender=request.user)
        unread_count = unread_msgs.count()

        # 2. Знаходимо ID ПЕРШОГО непрочитаного (тільки при першому завантаженні)
        first_unread_id = None
        if offset == 0 and unread_count > 0:
            first_unread = unread_msgs.order_by('created_at').first()
            first_unread_id = str(first_unread.id) if first_unread else None

        # 3. Відмічаємо їх як прочитані
        unread_msgs.update(is_read=True)

        # 4. Визначаємо ліміт (за замовчуванням 20). 
        # Але якщо у нас 35 непрочитаних, то віддаємо їх всі + 10 старих для контексту
        limit = 20
        if offset == 0 and unread_count > 20:
            limit = unread_count + 10

        # 5. Завантажуємо з бази
        messages_qs = chat.messages.select_related('sender__person').prefetch_related('images').order_by('-created_at')[offset:offset+limit]

        # Перевертаємо, щоб повідомлення йшли зверху вниз (хронологічно)
        messages_list = list(messages_qs)[::-1]

        data = []
        for msg in messages_list:
            images = [request.build_absolute_uri(img.image.url) for img in msg.images.all()]
            data.append({
                "id": str(msg.id),
                "sender_id": str(msg.sender.id),
                "text": msg.text,
                "images": images,
                "created_at": msg.created_at.isoformat()
            })

        has_more = chat.messages.count() > (offset + limit)

        return Response({
            "messages": data,
            "first_unread_id": first_unread_id,
            "has_more": has_more
        })

class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, participants=request.user)
        text = request.data.get('text', '').strip()
        images_data = request.FILES.getlist('images')

        # 🔥 ВАЛІДАЦІЯ 🔥
        if not text and not images_data:
            return Response({"error": "Повідомлення не може бути порожнім"}, status=400)
        if len(text) > 4096:
            return Response({"error": "Перевищено ліміт 4096 символів"}, status=400)
        if len(images_data) > 5:
            return Response({"error": "Максимум 5 картинок"}, status=400)

        for img in images_data:
            if not img.content_type.startswith('image/'):
                return Response({"error": f"Файл {img.name} не є зображенням!"}, status=400)

        # Створення
        message = Message.objects.create(chat=chat, sender=request.user, text=text)
        for img in images_data:
            MessageImage.objects.create(message=message, image=img)
            
        chat.updated_at = timezone.now()
        chat.save()

        # 🔥 СОКЕТИ: Повідомляємо співрозмовника 🔥
        other_users = chat.participants.exclude(id=request.user.id)
        for u in other_users:
            try:
                create_and_send_notification(
                    recipient=u, title="Нове повідомлення",
                    message=f"{request.user.person.get_full_name()} надіслав вам повідомлення.",
                    category='social', related_id=str(chat.id)
                )
            except Exception: pass

        return Response({"status": "sent"})

class GetOrCreateChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        # Шукаємо або створюємо чат між request.user та user_id
        target_user = get_object_or_404(User, id=user_id)
        if target_user == request.user:
            return Response({"error": "Неможливо створити чат із собою"}, status=400)

        # Шукаємо спільний чат
        chat = Chat.objects.filter(participants=request.user).filter(participants=target_user).first()
        
        if not chat:
            chat = Chat.objects.create()
            chat.participants.add(request.user, target_user)
            
        return Response({"chat_id": str(chat.id)})