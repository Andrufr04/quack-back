from django.urls import path
from .views import (
    AdminStudyGroupView, AllGroupsView, AllTeachersView, CreateLessonView, CreateTaskView, LessonDetailView, LessonListFilteringView, TasksTypeView, TeacherCurrentLessonView, TeacherGroupsView, TeacherSubjectsView, 
    TeacherTasksToCheckView, GradeTaskView,
    StudentTasksView, SubmitTaskWorkView
)

app_name = 'education'

urlpatterns = [
    path('types/', TasksTypeView.as_view(), name='task-types'),

    # Завдання (Teacher)
    path('my-groups/', TeacherGroupsView.as_view(), name='teacher-groups'),
    path('my-subjects/', TeacherSubjectsView.as_view(), name='teacher-subjects'),
    path('tasks/create/', CreateTaskView.as_view(), name='task-create'),
    path('tasks/to-check/', TeacherTasksToCheckView.as_view(), name='tasks-to-check'),
    path('tasks/grade/<uuid:submission_id>/', GradeTaskView.as_view(), name='task-grade'),
    
    path('teacher/current-lesson/', TeacherCurrentLessonView.as_view()),

    # Завдання (Student)
    path('tasks/my-tasks/', StudentTasksView.as_view(), name='student-tasks'),
    path('tasks/submit/', SubmitTaskWorkView.as_view(), name='task-submit'),

    # --- АДМІНІСТРУВАННЯ РОЗКЛАДУ ---
    path('lessons/filter/', LessonListFilteringView.as_view(), name='lessons-filter'),
    path('lessons/detail/<uuid:pk>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/create/', CreateLessonView.as_view(), name='lesson-create'),
    path('all-teachers/', AllTeachersView.as_view(), name='all-teachers'),
    path('all-groups/', AllGroupsView.as_view(), name='all-groups'),
    path('subjects/', TeacherSubjectsView.as_view(), name='all-subjects'),

    path('groups/', AdminStudyGroupView.as_view(), name='admin-groups'),
    path('groups/<uuid:pk>/', AdminStudyGroupView.as_view(), name='admin-group-detail'),
]