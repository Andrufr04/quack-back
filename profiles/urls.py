from django.urls import path
from .views import ChatListView, ChatMessagesView, CommentDeleteView, CommentListCreateView, GetOrCreateChatView, MyProfileView, PostDeleteView, PostListView, ReactionToggleView, SendMessageView, UserProfileView

urlpatterns = [
    path('my/', MyProfileView.as_view(), name='my-profile'),
    path('<uuid:user_id>/', UserProfileView.as_view(), name='user-profile'),

    path('posts/create/', PostListView.as_view()),
    path('posts/user/<uuid:user_id>/', PostListView.as_view()),
    path('posts/<uuid:post_id>/react/', ReactionToggleView.as_view()),
    path('posts/<uuid:post_id>/delete/', PostDeleteView.as_view()),

    path('posts/<uuid:post_id>/comments/', CommentListCreateView.as_view()),
    path('comments/<uuid:comment_id>/delete/', CommentDeleteView.as_view()),

    path('chats/', ChatListView.as_view()),
    path('chats/<uuid:chat_id>/', ChatMessagesView.as_view()),
    path('chats/<uuid:chat_id>/send/', SendMessageView.as_view()),
    path('chats/start/<uuid:user_id>/', GetOrCreateChatView.as_view()),

]