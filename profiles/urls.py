from django.urls import path
from .views import MyProfileView, PostDeleteView, PostListView, ReactionToggleView, UserProfileView

urlpatterns = [
    path('my/', MyProfileView.as_view(), name='my-profile'),
    path('<uuid:user_id>/', UserProfileView.as_view(), name='user-profile'),

    path('posts/create/', PostListView.as_view()),
    path('posts/user/<uuid:user_id>/', PostListView.as_view()),
    path('posts/<uuid:post_id>/react/', ReactionToggleView.as_view()),
    path('posts/<uuid:post_id>/delete/', PostDeleteView.as_view()),

]