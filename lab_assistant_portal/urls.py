from django.urls import path
from . import views

app_name = 'lab_assistant_portal'

urlpatterns = [
    # Main dashboard and profile pages
    path('', views.index, name='index'),
    path('profile/', views.profile, name='profile'),
    
    # Leave applications management
    path('leave-applications/', views.leave_applications, name='leave_applications'),
    path('leave-applications/<int:application_id>/', views.leave_application_detail, name='leave_application_detail'),
    path('approve-leave/<int:application_id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:application_id>/', views.reject_leave, name='reject_leave'),
    
    # Attendance exceptions management
    path('attendance-exceptions/', views.attendance_exceptions, name='attendance_exceptions'),
    path('create-exception/', views.create_exception, name='create_exception'),
    path('approve-exception/<int:exception_id>/', views.approve_exception, name='approve_exception'),
    path('reject-exception/<int:exception_id>/', views.reject_exception, name='reject_exception'),
    
    # Low attendance monitoring
    path('low-attendance/', views.low_attendance, name='low_attendance'),
    path('get-student-attendance-details/', views.get_student_attendance_details, name='get_student_attendance_details'),
    path('notify-student/<int:student_id>/', views.notify_student, name='notify_student'),
    
    # Lab schedule and management
    path('lab-schedule/', views.lab_schedule, name='lab_schedule'),
    path('get-session-details/', views.get_session_details, name='get_session_details'),
    path('get-session-attendance/', views.get_session_attendance, name='get_session_attendance'),
    path('report-lab-issue/', views.report_lab_issue, name='report_lab_issue'),
    path('mark-issue-resolved/', views.mark_issue_resolved, name='mark_issue_resolved'),
    
    # Reports generation
    path('reports/', views.reports, name='reports'),
    path('generate-report/', views.generate_report, name='generate_report'),
    path('view-report/', views.view_report, name='view_report'),
    path('schedule-report/', views.schedule_report, name='schedule_report'),
    path('share-report/', views.share_report, name='share_report'),
    path('get-scheduled-report-details/', views.get_scheduled_report_details, name='get_scheduled_report_details'),
    path('delete-scheduled-report/', views.delete_scheduled_report, name='delete_scheduled_report'),
    
    # Profile management
    path('update-profile/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('update-profile-photo/', views.update_profile_photo, name='update_profile_photo'),
    path('remove-profile-photo/', views.remove_profile_photo, name='remove_profile_photo'),
    path('update-notification-settings/', views.update_notification_settings, name='update_notification_settings'),
    
    # Utility endpoints
    path('log/', views.log, name='log'),
]