from django.urls import path
from . import views

app_name = 'student_portal'

urlpatterns = [
    # Dashboard
    path('', views.index, name='index'),
    path('dashboard/', views.index, name='dashboard'),
    
    # Attendance
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/subject/<int:subject_id>/', views.subject_attendance, name='subject_attendance'),
    path('attendance/history/', views.attendance_history, name='attendance_history'),
    
    # Timetable
    path('timetable/', views.timetable, name='timetable'),
    path('timetable/day/<str:day>/', views.day_timetable, name='day_timetable'),
    
    # Leave Applications
    path('leave/', views.leave_application, name='leave_application'),
    path('leave/create/', views.create_leave_application, name='create_leave_application'),
    path('leave/<int:leave_id>/', views.leave_application_detail, name='leave_application_detail'),
    path('leave/<int:leave_id>/cancel/', views.cancel_leave_application, name='cancel_leave_application'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Profile
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),

    path('log/', views.log_view, name='log'),
    
    # AJAX endpoints
    # path('api/attendance-data/', views.get_attendance_data, name='get_attendance_data'),
    # path('api/timetable-data/', views.get_timetable_data, name='get_timetable_data'),
    # path('api/notification-count/', views.get_notification_count, name='get_notification_count'),
]