from django.urls import path
from .views import (
    AdminNewsDetailView, AdminNewsView, AdminStudyGroupView, AllGroupsView, AllTeachersView, CalendarLessonsView, CreateLessonView, CreateTaskView, GradeLessonStudentView, LessonDetailView, LessonListFilteringView, LessonStudentsView, MarkNewsReadView, SetAttendanceView, StudentAttendanceHistoryView, StudentDashboardStatsView, StudentNewsView, TasksTypeView, TeacherCurrentLessonView, TeacherGroupsView, TeacherLessonsTodayView, TeacherSubjectsView, 
    TeacherTasksToCheckView, GradeTaskView,
    StudentTasksView, SubmitTaskWorkView, ToggleDuckView, UpdateLessonThemeView
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
    path('teacher/lessons-today/', TeacherLessonsTodayView.as_view()),
    path('lessons/<uuid:lesson_id>/students/', LessonStudentsView.as_view()),
    path('lessons/<uuid:lesson_id>/update-theme/', UpdateLessonThemeView.as_view()),
    path('lessons/<uuid:lesson_id>/students/<uuid:student_id>/toggle-duck/', ToggleDuckView.as_view()),
    path('attendance/', SetAttendanceView.as_view()),
    path('grade-student/', GradeLessonStudentView.as_view()),

    path('calendar/lessons/', CalendarLessonsView.as_view(), name='calendar-lessons'),

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
    
    path('student/dashboard-stats/', StudentDashboardStatsView.as_view(), name='student-stats'),
    path('student/attendance-history/', StudentAttendanceHistoryView.as_view(), name='student-attendance'),

    path('news/admin/', AdminNewsView.as_view(), name='admin-news'),
    path('news/admin/<uuid:news_id>/', AdminNewsDetailView.as_view(), name='admin-news-detail'),
    path('news/student/', StudentNewsView.as_view(), name='student-news'),
    path('news/<uuid:news_id>/read/', MarkNewsReadView.as_view(), name='mark-news-read'),
]