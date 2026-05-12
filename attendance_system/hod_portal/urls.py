from django.urls import path
from . import views

app_name = 'hod_portal'

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.index, name='dashboard'),
    path('reports/', views.department_reports, name='department_reports'),
    path('student-progression/', views.student_progression, name='student_progression'),
    path('electives/', views.elective_management, name='elective_management'),
    path('faculty-performance/', views.faculty_performance, name='faculty_performance'),
    path('attendance-analytics/', views.attendance_analytics, name='attendance_analytics'),
]