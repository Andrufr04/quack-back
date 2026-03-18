from django.urls import path
from .views import AdminCreateUserView, AdminManageUsersView

app_name = 'users'

urlpatterns = [
    path('admin-create/', AdminCreateUserView.as_view(), name='admin-create-user'),
    
    path('manage/', AdminManageUsersView.as_view(), name='admin-manage-users'),
    
    path('manage/<uuid:pk>/', AdminManageUsersView.as_view(), name='admin-manage-user-detail'),
]