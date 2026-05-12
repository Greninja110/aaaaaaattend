from django.urls import path
from . import views

app_name = 'faculty_portal'

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.index, name='dashboard'),
    path('timetable/', views.timetable, name='timetable'),
    path('attendance/', views.attendance_record, name='attendance_record'),
    path('attendance/record/<int:faculty_subject_id>/', views.record_attendance, name='record_attendance'),
    path('attendance/history/', views.attendance_history, name='attendance_history'),
    path('attendance/bulk/', views.bulk_attendance, name='bulk_attendance'),
    path('attendance/template/<int:faculty_subject_id>/', views.download_attendance_template, name='download_attendance_template'),
    path('leave/', views.leave_applications, name='leave_applications'),
    path('leave/approve/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('leave/reject/<int:leave_id>/', views.reject_leave, name='reject_leave'),
    path('reports/', views.reports, name='reports'),
]