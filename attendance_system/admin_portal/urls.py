# Add this to your urls.py file

from django.urls import path
from . import views

app_name = 'admin_portal'

urlpatterns = [
    # Dashboard
    path('', views.index, name='index'),
    path('dashboard/', views.index, name='dashboard'),

    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:user_id>/change-password/', views.change_password, name='change_password'),
    path('users/<int:user_id>/details/<str:role>/', views.user_additional_details, name='user_additional_details'),
    
    # Department Management
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:department_id>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:department_id>/delete/', views.department_delete, name='department_delete'),
    
    # Academic Year Management
    path('academic-years/', views.academic_year_list, name='academic_year_list'),
    path('academic-years/create/', views.academic_year_create, name='academic_year_create'),
    path('academic-years/<int:year_id>/edit/', views.academic_year_edit, name='academic_year_edit'),
    path('academic-years/<int:year_id>/delete/', views.academic_year_delete, name='academic_year_delete'),
    path('academic-years/<int:year_id>/set-current/', views.set_current_academic_year, name='set_current_academic_year'),
    
    # Subject Management
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:subject_id>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:subject_id>/delete/', views.subject_delete, name='subject_delete'),
    
    # Faculty Assignment
    path('faculty-assignment/', views.faculty_assignment_list, name='faculty_assignment_list'),
    path('faculty-assignment/create/', views.faculty_assignment_create, name='faculty_assignment_create'),
    path('faculty-assignment/<int:assignment_id>/edit/', views.faculty_assignment_edit, name='faculty_assignment_edit'),
    path('faculty-assignment/<int:assignment_id>/delete/', views.faculty_assignment_delete, name='faculty_assignment_delete'),
    
    # Existing timetable path
    path('timetable/', views.timetable_view, name='timetable'),
    path('timetable/create/', views.timetable_create, name='timetable_create'),
    path('timetable/<int:timetable_id>/edit/', views.timetable_edit, name='timetable_edit'),
    path('timetable/<int:timetable_id>/delete/', views.timetable_delete, name='timetable_delete'),
    path('ajax/get-faculty-subjects/', views.get_faculty_subjects, name='get_faculty_subjects'),

    # System logs
    path('logs/', views.system_logs, name='system_logs'),
    path('logs/export/', views.export_system_logs, name='export_system_logs'),
    
    
    # AJAX endpoints
    path('ajax/subjects-by-department/', views.get_subjects_by_department, name='get_subjects_by_department'),
    path('ajax/class-sections-by-department/', views.get_class_sections_by_department, name='get_class_sections_by_department'),
    
    # Reports
    path('reports/', views.report_dashboard, name='report_dashboard'),
    path('reports/attendance/', views.attendance_report, name='attendance_report'),
    path('reports/faculty-workload/', views.faculty_workload_report, name='faculty_workload_report'),
    
    # Bulk Import
    path('import/', views.bulk_import_users, name='bulk_import_users'),
    path('import/results/<int:log_id>/', views.import_results, name='import_results'),
    path('import/template/<str:import_type>/', views.download_import_template, name='download_import_template'),
    
    # Settings
    path('settings/', views.settings_page, name='settings'),
]