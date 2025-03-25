from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
import logging
import json

# Set up logging
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('lab_assistant_portal.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

@login_required
def index(request):
    """Lab Assistant Dashboard view"""
    logger.info(f"User {request.user.username} accessed the lab assistant dashboard")
    user = request.user
    # Check if user has lab_assistant role
    if user.get_role() != 'lab_assistant':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to access the Lab Assistant Portal.',
            'return_url': '/'
        })
    
    # Mock data for dashboard
    context = {
        'pending_leave_count': 5,
        'todays_lab_sessions': 8,
        'todays_labs_count': 3,
        'low_attendance_count': 12,
        'approved_leaves_month': 24,
        'lab_schedule': []  # This would be populated from the database
    }
    
    return render(request, 'lab_assistant_portal/index.html', context)

@login_required
def profile(request):
    """Lab assistant profile view"""
    logger.info(f"User {request.user.username} accessed their profile")
    
    # Mock context data
    context = {
        'user': request.user,
        'lab_assistant': {
            'department': {'department_name': 'Computer Engineering'},
            'employee_id': 'LA001',
            'joining_year': 2020,
            'dob': '1990-01-01',
            'status': 'active',
            'contact_number': '+1234567890'
        },
        'leave_approved_count': 45,
        'exceptions_count': 23,
        'dept_count': 2,
        'recent_activities': [],  # This would be populated from the database
        'notification_settings': {
            'email_leave_applications': True,
            'email_attendance_exceptions': True,
            'email_low_attendance': False,
            'portal_leave_applications': True,
            'portal_attendance_exceptions': True,
            'portal_low_attendance': True,
        }
    }
    
    return render(request, 'lab_assistant_portal/profile.html', context)

@login_required
def leave_applications(request):
    """View for managing leave applications"""
    logger.info(f"User {request.user.username} accessed leave applications")
    
    # Mock data for leave applications
    context = {
        'pending_count': 8,
        'approved_count': 25,
        'rejected_count': 5,
        'avg_processing_hours': 6,
        'pending_percentage': 20,
        'approved_percentage': 65,
        'rejected_percentage': 15,
        'departments': [],  # This would be populated from the database
        'semester_range': range(1, 9),
        'applications': []  # This would be populated from the database
    }
    
    return render(request, 'lab_assistant_portal/leave_applications.html', context)

@login_required
def leave_application_detail(request, application_id):
    """View details of a specific leave application"""
    logger.info(f"User {request.user.username} accessed leave application {application_id}")
    
    # Mock leave application data
    application = {
        'id': application_id,
        'student_name': 'John Doe',
        'roll_number': 'CE21001',
        'department': 'Computer Engineering',
        'semester': 4,
        'start_date': '2025-03-15',
        'end_date': '2025-03-18',
        'reason': 'Medical',
        'status': 'pending'
    }
    
    return render(request, 'lab_assistant_portal/leave_application_detail.html', {'application': application})

@login_required
def approve_leave(request, application_id):
    """Approve a leave application"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} approved leave application {application_id}")
        messages.success(request, "Leave application approved successfully.")
    
    return redirect('lab_assistant_portal:leave_applications')

@login_required
def reject_leave(request, application_id):
    """Reject a leave application"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} rejected leave application {application_id}")
        messages.success(request, "Leave application rejected successfully.")
    
    return redirect('lab_assistant_portal:leave_applications')

@login_required
def attendance_exceptions(request):
    """View for managing attendance exceptions"""
    logger.info(f"User {request.user.username} accessed attendance exceptions")
    
    # Mock data for attendance exceptions
    context = {
        'pending_count': 7,
        'approved_count': 18,
        'rejected_count': 3,
        'dont_care_count': 12,
        'pending_percentage': 18,
        'approved_percentage': 45,
        'rejected_percentage': 7,
        'dont_care_percentage': 30,
        'departments': [],  # This would be populated from the database
        'semester_range': range(1, 9),
        'exceptions': []  # This would be populated from the database
    }
    
    return render(request, 'lab_assistant_portal/attendance_exceptions.html', context)

@login_required
def create_exception(request):
    """Create a new attendance exception"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} created a new attendance exception")
        messages.success(request, "Attendance exception created successfully.")
    
    return redirect('lab_assistant_portal:attendance_exceptions')

@login_required
def approve_exception(request, exception_id):
    """Approve an attendance exception"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} approved attendance exception {exception_id}")
        messages.success(request, "Attendance exception approved successfully.")
    
    return redirect('lab_assistant_portal:attendance_exceptions')

@login_required
def reject_exception(request, exception_id):
    """Reject an attendance exception"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} rejected attendance exception {exception_id}")
        messages.success(request, "Attendance exception rejected successfully.")
    
    return redirect('lab_assistant_portal:attendance_exceptions')

@login_required
def low_attendance(request):
    """View for monitoring students with low attendance"""
    logger.info(f"User {request.user.username} accessed low attendance monitoring")
    
    # Mock data for low attendance
    context = {
        'total_students': 120,
        'warning_count': 15,
        'critical_count': 8,
        'good_count': 97,
        'warning_percentage': 12.5,
        'critical_percentage': 6.7,
        'good_percentage': 80.8,
        'departments': [],  # This would be populated from the database
        'subjects': [],  # This would be populated from the database
        'low_attendance_students': []  # This would be populated from the database
    }
    
    return render(request, 'lab_assistant_portal/low_attendance.html', context)

@login_required
def get_student_attendance_details(request):
    """AJAX endpoint to get detailed attendance for a student"""
    student_id = request.GET.get('student_id')
    logger.info(f"User {request.user.username} requested attendance details for student {student_id}")
    
    # Mock response data
    response_data = {
        'success': True,
        'data': {
            'student_name': 'John Doe',
            'roll_number': 'CE21001',
            'department': 'Computer Engineering',
            'semester': 4,
            'attendance_percentage': 68
        },
        'html': '<div>Student attendance details would be rendered here</div>'
    }
    
    return JsonResponse(response_data)

@login_required
def notify_student(request, student_id):
    """Notify a student about their low attendance"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} sent a notification to student {student_id}")
        messages.success(request, "Notification sent successfully.")
    
    return redirect('lab_assistant_portal:low_attendance')

@login_required
def lab_schedule(request):
    """View for lab schedule"""
    logger.info(f"User {request.user.username} accessed lab schedule")
    
    # Mock data for lab schedule
    context = {
        'labs': [],  # This would be populated from the database
        'batches': [],  # This would be populated from the database
        'weekly_schedule': {
            'time_slots': [],
            'breaks': []
        },
        'all_sessions': [],  # This would be populated from the database
        'equipment_status': [],  # This would be populated from the database
        'recent_issues': []  # This would be populated from the database
    }
    
    return render(request, 'lab_assistant_portal/lab_schedule.html', context)

@login_required
def get_session_details(request):
    """AJAX endpoint to get lab session details"""
    session_id = request.GET.get('session_id')
    logger.info(f"User {request.user.username} requested details for lab session {session_id}")
    
    # Mock response data
    response_data = {
        'success': True,
        'data': {
            'subject_name': 'Database Systems Lab',
            'faculty_name': 'Prof. Smith',
            'batch_name': 'Batch A',
            'lab_name': 'Computer Lab 1',
            'day_of_week': 'Monday',
            'start_time': '10:00 AM',
            'end_time': '12:00 PM'
        },
        'html': '<div>Session details would be rendered here</div>'
    }
    
    return JsonResponse(response_data)

@login_required
def get_session_attendance(request):
    """AJAX endpoint to get attendance for a lab session"""
    session_id = request.GET.get('session_id')
    logger.info(f"User {request.user.username} requested attendance for lab session {session_id}")
    
    # Mock response data
    response_data = {
        'success': True,
        'data': {
            'subject_name': 'Database Systems Lab',
            'date': '2025-03-15',
            'present_count': 18,
            'absent_count': 2,
            'total_students': 20
        },
        'html': '<div>Attendance details would be rendered here</div>'
    }
    
    return JsonResponse(response_data)

@login_required
def report_lab_issue(request):
    """Report an issue with a lab"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} reported a lab issue")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def mark_issue_resolved(request):
    """Mark a lab issue as resolved"""
    if request.method == 'POST':
        issue_id = request.POST.get('issue_id')
        logger.info(f"User {request.user.username} marked lab issue {issue_id} as resolved")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def reports(request):
    """View for generating reports"""
    logger.info(f"User {request.user.username} accessed reports")
    
    # Mock data for reports
    context = {
        'departments': [],  # This would be populated from the database
        'labs': [],  # This would be populated from the database
        'batches': [],  # This would be populated from the database
        'subjects': [],  # This would be populated from the database
        'recent_reports': [],  # This would be populated from the database
        'scheduled_reports': []  # This would be populated from the database
    }
    
    return render(request, 'lab_assistant_portal/reports.html', context)

@login_required
def generate_report(request):
    """Generate a new report"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        logger.info(f"User {request.user.username} generated a {report_type} report")
        
        # Mock response data
        response_data = {
            'success': True,
            'html': '<div>Report would be rendered here</div>',
            'charts': {}  # Chart data would go here
        }
        
        return JsonResponse(response_data)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def view_report(request):
    """View a previously generated report"""
    report_id = request.GET.get('report_id')
    logger.info(f"User {request.user.username} viewed report {report_id}")
    
    # Mock response data
    response_data = {
        'success': True,
        'html': '<div>Report would be rendered here</div>',
        'charts': {}  # Chart data would go here
    }
    
    return JsonResponse(response_data)

@login_required
def schedule_report(request):
    """Schedule a report for automatic generation"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} scheduled a new report")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def share_report(request):
    """Share a report with others"""
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        logger.info(f"User {request.user.username} shared report {report_id}")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def get_scheduled_report_details(request):
    """AJAX endpoint to get details of a scheduled report"""
    report_id = request.GET.get('report_id')
    logger.info(f"User {request.user.username} requested details for scheduled report {report_id}")
    
    # Mock response data
    response_data = {
        'success': True,
        'data': {
            'name': 'Monthly Attendance Report',
            'type': 'Attendance',
            'frequency': 'Monthly',
            'next_run': '2025-04-01',
            'recipients': 'admin@example.com, hod@example.com',
            'format': 'PDF',
            'status': 'Active',
            'filters': 'Department: Computer Engineering'
        }
    }
    
    return JsonResponse(response_data)

@login_required
def delete_scheduled_report(request):
    """Delete a scheduled report"""
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        logger.info(f"User {request.user.username} deleted scheduled report {report_id}")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def update_profile(request):
    """Update lab assistant profile"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} updated their profile")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def change_password(request):
    """Change lab assistant password"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} changed their password")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def update_profile_photo(request):
    """Update lab assistant profile photo"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} updated their profile photo")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def remove_profile_photo(request):
    """Remove lab assistant profile photo"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} removed their profile photo")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def update_notification_settings(request):
    """Update notification settings"""
    if request.method == 'POST':
        logger.info(f"User {request.user.username} updated their notification settings")
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def log(request):
    """Endpoint for client-side logging"""
    if request.method == 'POST':
        message = request.POST.get('message', '')
        log_type = request.POST.get('type', 'info')
        
        if log_type == 'error':
            logger.error(f"[CLIENT] {message}")
        elif log_type == 'warning':
            logger.warning(f"[CLIENT] {message}")
        else:
            logger.info(f"[CLIENT] {message}")
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})