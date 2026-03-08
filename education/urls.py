from django.urls import path
from .views import StudentTasksView

urlpatterns = [
    path('my/', StudentTasksView.as_view(), name='my-tasks'),
]