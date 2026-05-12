from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.urls import reverse
from django.db.models import Count, Q, F, Sum, Case, When, Value, IntegerField, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from datetime import datetime, timedelta, date
import csv
import json
import logging
import os
import io
import tempfile
from .forms import (
    LeaveApplicationApprovalForm, AttendanceExceptionForm, AttendanceExceptionApprovalForm, 
    LabIssueForm, LabIssueResolutionForm, ScheduledReportForm, ProfileUpdateForm, 
    PasswordChangeForm, NotificationSettingsForm, LeaveFilterForm, AttendanceExceptionFilterForm,
    LowAttendanceFilterForm, ReportGenerationForm
)
from core.models import (
    Department, Student, Faculty, Subject, ClassSection, Batch, 
    AcademicYear, SystemLog, FacultySubject, Attendance, LeaveApplication
)
from .models import LabAssistant, AttendanceException, LabIssue, ScheduledReport
from authentication.models import User
from django.contrib.auth.hashers import check_password, make_password

# Set up logging
logger = logging.getLogger(__name__)
log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'lab_assistant_portal.log')
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

def lab_assistant_required(view_func):
    """Decorator to check if user has lab_assistant role"""
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.get_role() != 'lab_assistant':
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to access the Lab Assistant Portal.',
                'return_url': '/'
            })
        return view_func(request, *args, **kwargs)
    return wrapper

def get_lab_assistant(user):
    """Helper function to get lab assistant object for a user"""
    try:
        return LabAssistant.objects.get(user=user)
    except LabAssistant.DoesNotExist:
        return None

def log_action(user, action, details=None, ip_address=None):
    """Helper function to log system actions"""
    SystemLog.objects.create(
        user=user,
        action=action,
        details=details,
        ip_address=ip_address or '0.0.0.0'
    )
    logger.info(f"User {user.username} performed action: {action}")

@login_required
@lab_assistant_required
def index(request):
    """Lab Assistant Dashboard view"""
    user = request.user
    logger.info(f"User {user.username} (ID: {user.user_id}) accessed the lab assistant dashboard")
    logger.info(f"User role: {user.get_role()}")
    
    lab_assistant = get_lab_assistant(user)
    logger.info(f"Lab assistant profile found: {lab_assistant is not None}")
    
    if not lab_assistant:
        # Return an error page instead of redirecting
        return render(request, 'error.html', {
            'error_title': 'Profile Not Found',
            'error_heading': 'Missing Lab Assistant Profile',
            'error_message': 'Your lab assistant profile is not set up yet. Please contact the administrator.',
            'return_url': '/'
        })
    
    # Get current academic year
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    
    # Dashboard statistics
    pending_leave_count = LeaveApplication.objects.filter(
        status='faculty_approved',
        student__department=lab_assistant.department
    ).count()
    
    # Get today's date
    today = timezone.now().date()
    
    # Get lab sessions for today
    todays_lab_sessions = FacultySubject.objects.filter(
        is_lab=True,
        class_section__department=lab_assistant.department,
        academic_year=current_academic_year
    ).count()
    
    # Count unique labs used today
    todays_labs = Attendance.objects.filter(
        attendance_date=today,
        faculty_subject__is_lab=True,
        student__department=lab_assistant.department
    ).values('faculty_subject__subject').distinct().count()
    
    # Get students with low attendance
    low_attendance_threshold = 75  # Default threshold
    low_attendance_count = 0
    
    # Get attendance stats
    if current_academic_year:
        # Get all students in the department
        students = Student.objects.filter(department=lab_assistant.department)
        
        # For each student, check if their attendance is below threshold
        for student in students:
            attendance_records = Attendance.objects.filter(
                student=student,
                faculty_subject__academic_year=current_academic_year,
                status__in=['present', 'absent']
            )
            
            if attendance_records.exists():
                total_classes = attendance_records.count()
                present_classes = attendance_records.filter(status='present').count()
                
                attendance_percentage = (present_classes / total_classes) * 100 if total_classes > 0 else 100
                
                if attendance_percentage < low_attendance_threshold:
                    low_attendance_count += 1
    
    # Approved leaves in the current month
    current_month = timezone.now().month
    current_year = timezone.now().year
    approved_leaves_month = LeaveApplication.objects.filter(
        status='lab_approved',
        lab_assistant_approval=lab_assistant,
        created_at__month=current_month,
        created_at__year=current_year
    ).count()
    
    # Get lab schedule
    lab_schedule = []
    today_weekday = today.strftime('%A')
    
    # Get timetable entries for today's labs
    timetable_entries = FacultySubject.objects.filter(
        is_lab=True,
        class_section__department=lab_assistant.department,
        academic_year=current_academic_year
    ).select_related('faculty', 'subject', 'class_section', 'batch')
    
    from django.db import connections
    cursor = connections['default'].cursor()
    
    # Execute a raw SQL query to get timetable for today
    cursor.execute('''
        SELECT t.start_time, t.end_time, t.room_number, s.subject_name, u.full_name as faculty_name,
               b.batch_name, cs.section_name
        FROM timetable t
        JOIN faculty_subject fs ON t.faculty_subject_id = fs.faculty_subject_id
        JOIN subjects s ON fs.subject_id = s.subject_id
        JOIN faculty f ON fs.faculty_id = f.faculty_id
        JOIN users u ON f.user_id = u.user_id
        LEFT JOIN batches b ON fs.batch_id = b.batch_id
        LEFT JOIN class_sections cs ON fs.class_section_id = cs.class_section_id
        WHERE fs.is_lab = TRUE
        AND t.day_of_week = %s
        AND fs.academic_year_id = %s
        AND EXISTS (
            SELECT 1 FROM class_sections cs2
            WHERE cs2.class_section_id = fs.class_section_id
            AND cs2.department_id = %s
        )
        ORDER BY t.start_time
    ''', [today_weekday, current_academic_year.academic_year_id if current_academic_year else 0, lab_assistant.department.department_id])
    
    lab_schedule = []
    for row in cursor.fetchall():
        start_time, end_time, room_number, subject_name, faculty_name, batch_name, section_name = row
        lab_schedule.append({
            'start_time': start_time,
            'end_time': end_time,
            'room': room_number,
            'subject': subject_name,
            'faculty': faculty_name,
            'batch': batch_name or 'All',
            'section': section_name or 'All'
        })
    
    context = {
        'lab_assistant': lab_assistant,
        'pending_leave_count': pending_leave_count,
        'todays_lab_sessions': todays_lab_sessions,
        'todays_labs_count': todays_labs,
        'low_attendance_count': low_attendance_count,
        'approved_leaves_month': approved_leaves_month,
        'lab_schedule': lab_schedule,
        'today': today
    }
    
    return render(request, 'lab_assistant_portal/index.html', context)

@login_required
@lab_assistant_required
def profile(request):
    """Lab assistant profile view"""
    logger.info(f"User {request.user.username} accessed their profile")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        return render(request, 'lab_assistant_portal/setup_required.html', {
            'error_title': 'Profile Not Found',
            'error_message': 'Your lab assistant profile is not set up yet. Please contact the administrator.'})
    
    # Get department info
    department = lab_assistant.department
    
    # Get leaves approved count
    leave_approved_count = LeaveApplication.objects.filter(
        lab_assistant_approval=lab_assistant,
        status='lab_approved'
    ).count()
    
    # Get attendance exceptions count
    exceptions_count = AttendanceException.objects.filter(
        lab_assistant=lab_assistant,
        status='approved'
    ).count()
    
    # Get departments count for lab assistant
    dept_count = 1  # Typically a lab assistant is assigned to one department
    
    # Get recent activities
    recent_activities = SystemLog.objects.filter(
        user=user
    ).order_by('-created_at')[:10]
    
    # Mock notification settings - in real implementation, this would be saved in the database
    notification_settings = {
        'email_leave_applications': True,
        'email_attendance_exceptions': True,
        'email_low_attendance': False,
        'portal_leave_applications': True,
        'portal_attendance_exceptions': True,
        'portal_low_attendance': True,
    }
    
    context = {
        'user': user,
        'lab_assistant': {
            'department': department,
            'employee_id': f"LA{lab_assistant.assistant_id:03d}",
            'joining_year': lab_assistant.joining_year,
            'dob': lab_assistant.dob,
            'status': lab_assistant.status,
            'contact_number': user.username  # Assuming username could be used as contact
        },
        'leave_approved_count': leave_approved_count,
        'exceptions_count': exceptions_count,
        'dept_count': dept_count,
        'recent_activities': recent_activities,
        'notification_settings': notification_settings
    }
    
    return render(request, 'lab_assistant_portal/profile.html', context)

@login_required
@lab_assistant_required
def leave_applications(request):
    """View for managing leave applications"""
    logger.info(f"User {request.user.username} accessed leave applications")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
        return redirect('/')
    
    # Get all departments
    departments = Department.objects.all()
    
    # Create filter form
    filter_form = LeaveFilterForm(request.GET, departments=departments)
    
    # Start with all faculty-approved leave applications
    applications = LeaveApplication.objects.filter(
        status='faculty_approved',
        student__department=lab_assistant.department
    ).select_related('student', 'student__user', 'student__department', 'faculty_approval')
    
    # Apply filters if form is valid
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        department_id = filter_form.cleaned_data.get('department')
        semester = filter_form.cleaned_data.get('semester')
        from_date = filter_form.cleaned_data.get('from_date')
        to_date = filter_form.cleaned_data.get('to_date')
        
        if status:
            applications = applications.filter(status=status)
        
        if department_id:
            applications = applications.filter(student__department_id=department_id)
        
        if semester:
            applications = applications.filter(student__current_semester=semester)
        
        if from_date:
            applications = applications.filter(start_date__gte=from_date)
        
        if to_date:
            applications = applications.filter(end_date__lte=to_date)
    
    # Count by status
    pending_count = LeaveApplication.objects.filter(status='faculty_approved').count()
    approved_count = LeaveApplication.objects.filter(status='lab_approved').count()
    rejected_count = LeaveApplication.objects.filter(status='rejected').count()
    total_count = pending_count + approved_count + rejected_count
    
    # Calculate percentages
    pending_percentage = (pending_count / total_count * 100) if total_count > 0 else 0
    approved_percentage = (approved_count / total_count * 100) if total_count > 0 else 0
    rejected_percentage = (rejected_count / total_count * 100) if total_count > 0 else 0
    
    # Calculate average processing time (hours)
    processed_applications = LeaveApplication.objects.filter(
        status__in=['lab_approved', 'rejected'],
        created_at__isnull=False
    )
    
    total_hours = 0
    count = 0
    for app in processed_applications:
        if app.created_at and app.created_at:
            delta = app.created_at - app.created_at
            hours = delta.total_seconds() / 3600
            total_hours += hours
            count += 1
    
    avg_processing_hours = round(total_hours / count, 1) if count > 0 else 0
    
    # Paginate applications
    paginator = Paginator(applications.order_by('-created_at'), 10)  # 10 applications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'avg_processing_hours': avg_processing_hours,
        'pending_percentage': round(pending_percentage, 1),
        'approved_percentage': round(approved_percentage, 1),
        'rejected_percentage': round(rejected_percentage, 1),
        'departments': departments,
        'semester_range': range(1, 9),
        'filter_form': filter_form,
        'applications': page_obj,
        'lab_assistant': lab_assistant
    }
    
    return render(request, 'lab_assistant_portal/leave_applications.html', context)

@login_required
@lab_assistant_required
def leave_application_detail(request, application_id):
    """View details of a specific leave application"""
    logger.info(f"User {request.user.username} accessed leave application {application_id}")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
        return redirect('/')
    
    # Get leave application
    application = get_object_or_404(LeaveApplication, leave_id=application_id)
    
    # Check if lab assistant has permission to view this application
    if application.student.department != lab_assistant.department:
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to view this leave application.',
            'return_url': reverse('lab_assistant_portal:leave_applications')
        })
    
    # Get student and calculate leave days
    student = application.student
    leave_days = (application.end_date - application.start_date).days + 1
    
    # Get form for approval
    form = LeaveApplicationApprovalForm(instance=application)
    
    # Get other leave applications for this student
    other_applications = LeaveApplication.objects.filter(
        student=student
    ).exclude(
        leave_id=application_id
    ).order_by('-created_at')[:5]
    
    context = {
        'application': application,
        'student': student,
        'leave_days': leave_days,
        'form': form,
        'other_applications': other_applications,
        'lab_assistant': lab_assistant
    }
    
    return render(request, 'lab_assistant_portal/leave_application_detail.html', context)

@login_required
@lab_assistant_required
def approve_leave(request, application_id):
    """Approve a leave application"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
            return redirect('/')
        
        # Get leave application
        application = get_object_or_404(LeaveApplication, leave_id=application_id)
        
        # Check if lab assistant has permission
        if application.student.department != lab_assistant.department:
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to approve this leave application.',
                'return_url': reverse('lab_assistant_portal:leave_applications')
            })
        
        # Check if application is in correct state
        if application.status != 'faculty_approved':
            messages.error(request, "This leave application cannot be approved in its current state.")
            return redirect('lab_assistant_portal:leave_application_detail', application_id=application_id)
        
        # Update application
        application.status = 'lab_approved'
        application.lab_assistant_approval = lab_assistant
        application.save()
        
        # Log the action
        log_action(
            user=user,
            action=f"Approved leave application #{application_id}",
            details=f"Leave for student {application.student.user.full_name} ({application.student.roll_number}) approved",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} approved leave application {application_id}")
        messages.success(request, "Leave application approved successfully.")
    
    return redirect('lab_assistant_portal:leave_applications')

@login_required
@lab_assistant_required
def reject_leave(request, application_id):
    """Reject a leave application"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
            return redirect('/')
        
        # Get leave application
        application = get_object_or_404(LeaveApplication, leave_id=application_id)
        
        # Check if lab assistant has permission
        if application.student.department != lab_assistant.department:
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to reject this leave application.',
                'return_url': reverse('lab_assistant_portal:leave_applications')
            })
        
        # Check if application is in correct state
        if application.status != 'faculty_approved':
            messages.error(request, "This leave application cannot be rejected in its current state.")
            return redirect('lab_assistant_portal:leave_application_detail', application_id=application_id)
        
        # Update application
        application.status = 'rejected'
        application.lab_assistant_approval = lab_assistant
        application.save()
        
        # Get rejection reason if provided
        reason = request.POST.get('comments', '')
        
        # Log the action
        log_action(
            user=user,
            action=f"Rejected leave application #{application_id}",
            details=f"Leave for student {application.student.user.full_name} ({application.student.roll_number}) rejected. Reason: {reason}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} rejected leave application {application_id}")
        messages.success(request, "Leave application rejected successfully.")
    
    return redirect('lab_assistant_portal:leave_applications')

@login_required
@lab_assistant_required
def attendance_exceptions(request):
    """View for managing attendance exceptions"""
    logger.info(f"User {request.user.username} accessed attendance exceptions")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
        return redirect('/')
    
    # Get all departments
    departments = Department.objects.all()
    
    # Create filter form
    filter_form = AttendanceExceptionFilterForm(request.GET, departments=departments)
    
    # Start with all pending exceptions for this department
    exceptions = AttendanceException.objects.filter(
        attendance__student__department=lab_assistant.department
    ).select_related(
        'attendance', 'attendance__student', 'attendance__student__user',
        'attendance__student__department', 'requested_by', 'requested_by__user'
    )
    
    # Apply filters if form is valid
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        department_id = filter_form.cleaned_data.get('department')
        requested_status = filter_form.cleaned_data.get('requested_status')
        from_date = filter_form.cleaned_data.get('from_date')
        to_date = filter_form.cleaned_data.get('to_date')
        
        if status:
            exceptions = exceptions.filter(status=status)
        
        if department_id:
            exceptions = exceptions.filter(attendance__student__department_id=department_id)
        
        if requested_status:
            exceptions = exceptions.filter(requested_status=requested_status)
        
        if from_date:
            exceptions = exceptions.filter(created_at__date__gte=from_date)
        
        if to_date:
            exceptions = exceptions.filter(created_at__date__lte=to_date)
    
    # Count by status
    pending_count = AttendanceException.objects.filter(status='pending').count()
    approved_count = AttendanceException.objects.filter(status='approved').count()
    rejected_count = AttendanceException.objects.filter(status='rejected').count()
    dont_care_count = Attendance.objects.filter(status='dont_care').count()
    
    total_count = pending_count + approved_count + rejected_count + dont_care_count
    
    # Calculate percentages
    pending_percentage = (pending_count / total_count * 100) if total_count > 0 else 0
    approved_percentage = (approved_count / total_count * 100) if total_count > 0 else 0
    rejected_percentage = (rejected_count / total_count * 100) if total_count > 0 else 0
    dont_care_percentage = (dont_care_count / total_count * 100) if total_count > 0 else 0
    
    # Paginate exceptions
    paginator = Paginator(exceptions.order_by('-created_at'), 10)  # 10 exceptions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'dont_care_count': dont_care_count,
        'pending_percentage': round(pending_percentage, 1),
        'approved_percentage': round(approved_percentage, 1),
        'rejected_percentage': round(rejected_percentage, 1),
        'dont_care_percentage': round(dont_care_percentage, 1),
        'departments': departments,
        'semester_range': range(1, 9),
        'filter_form': filter_form,
        'exceptions': page_obj,
        'lab_assistant': lab_assistant
    }
    
    return render(request, 'lab_assistant_portal/attendance_exceptions.html', context)

@login_required
@lab_assistant_required
def create_exception(request):
    """Create a new attendance exception"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
            return redirect('/')
        
        form = AttendanceExceptionForm(request.POST)
        
        if form.is_valid():
            exception = form.save(commit=False)
            
            # Check if attendance record belongs to department of lab assistant
            attendance = exception.attendance
            if attendance.student.department != lab_assistant.department:
                messages.error(request, "You can only create exceptions for students in your department.")
                return redirect('lab_assistant_portal:attendance_exceptions')
            
            # Save previous status
            exception.previous_status = attendance.status
            
            # Auto-approve the exception as it's created by lab assistant
            exception.status = 'approved'
            exception.lab_assistant = lab_assistant
            exception.save()
            
            # Update the attendance record
            attendance.status = exception.requested_status
            attendance.save()
            
            # Log the action
            log_action(
                user=user,
                action=f"Created attendance exception for {attendance.student.user.full_name}",
                details=f"Changed status from {exception.previous_status} to {exception.requested_status} for date {attendance.attendance_date}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} created a new attendance exception")
            messages.success(request, "Attendance exception created successfully.")
        else:
            messages.error(request, "Error creating attendance exception. Please check the form and try again.")
    
    return redirect('lab_assistant_portal:attendance_exceptions')

@login_required
@lab_assistant_required
def approve_exception(request, exception_id):
    """Approve an attendance exception"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
            return redirect('/')
        
        # Get exception
        exception = get_object_or_404(AttendanceException, exception_id=exception_id)
        
        # Check if lab assistant has permission
        if exception.attendance.student.department != lab_assistant.department:
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to approve this attendance exception.',
                'return_url': reverse('lab_assistant_portal:attendance_exceptions')
            })
        
        # Check if exception is in correct state
        if exception.status != 'pending':
            messages.error(request, "This attendance exception cannot be approved in its current state.")
            return redirect('lab_assistant_portal:attendance_exceptions')
        
        # Update exception
        exception.status = 'approved'
        exception.lab_assistant = lab_assistant
        exception.save()
        
        # Update the attendance record
        attendance = exception.attendance
        attendance.status = exception.requested_status
        attendance.save()
        
        # Log the action
        log_action(
            user=user,
            action=f"Approved attendance exception #{exception_id}",
            details=f"Changed status from {exception.previous_status} to {exception.requested_status} for student {attendance.student.user.full_name}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} approved attendance exception {exception_id}")
        messages.success(request, "Attendance exception approved successfully.")
    
    return redirect('lab_assistant_portal:attendance_exceptions')

@login_required
@lab_assistant_required
def reject_exception(request, exception_id):
    """Reject an attendance exception"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
            return redirect('/')
        
        # Get exception
        exception = get_object_or_404(AttendanceException, exception_id=exception_id)
        
        # Check if lab assistant has permission
        if exception.attendance.student.department != lab_assistant.department:
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to reject this attendance exception.',
                'return_url': reverse('lab_assistant_portal:attendance_exceptions')
            })
        
        # Check if exception is in correct state
        if exception.status != 'pending':
            messages.error(request, "This attendance exception cannot be rejected in its current state.")
            return redirect('lab_assistant_portal:attendance_exceptions')
        
        # Update exception
        exception.status = 'rejected'
        exception.lab_assistant = lab_assistant
        exception.save()
        
        # Get rejection reason if provided
        reason = request.POST.get('comments', '')
        
        # Log the action
        log_action(
            user=user,
            action=f"Rejected attendance exception #{exception_id}",
            details=f"Rejected request to change status from {exception.previous_status} to {exception.requested_status}. Reason: {reason}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} rejected attendance exception {exception_id}")
        messages.success(request, "Attendance exception rejected successfully.")
    
    return redirect('lab_assistant_portal:attendance_exceptions')

@login_required
@lab_assistant_required
def low_attendance(request):
    """View for monitoring students with low attendance"""
    logger.info(f"User {request.user.username} accessed low attendance monitoring")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
        return redirect('/')
    
    # Get current academic year
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    
    # Get all departments
    departments = Department.objects.all()
    
    # Get all subjects
    subjects = Subject.objects.filter(department=lab_assistant.department).order_by('subject_name')
    
    # Create filter form
    filter_form = LowAttendanceFilterForm(request.GET, departments=departments, subjects=subjects)
    
    # Default threshold
    threshold = 75
    department_id = None
    semester = None
    subject_id = None
    
    # Apply filters if form is valid
    if filter_form.is_valid():
        department_id = filter_form.cleaned_data.get('department')
        semester = filter_form.cleaned_data.get('semester')
        threshold = filter_form.cleaned_data.get('threshold', 75)
        subject_id = filter_form.cleaned_data.get('subject')
    
    # Get students with low attendance
    low_attendance_students = []
    
    # Get all students in the department or filtered department
    students_query = Student.objects.filter(status='active')
    
    if department_id:
        students_query = students_query.filter(department_id=department_id)
    else:
        students_query = students_query.filter(department=lab_assistant.department)
    
    if semester:
        students_query = students_query.filter(current_semester=semester)
    
    students = students_query.select_related('user', 'department', 'class_section', 'batch')
    
    for student in students:
        # Get attendance records for the student
        attendance_query = Attendance.objects.filter(
            student=student,
            status__in=['present', 'absent']
        )
        
        if current_academic_year:
            attendance_query = attendance_query.filter(
                faculty_subject__academic_year=current_academic_year
            )
        
        if subject_id:
            attendance_query = attendance_query.filter(
                faculty_subject__subject_id=subject_id
            )
        
        # Count total and present classes
        total_classes = attendance_query.count()
        present_classes = attendance_query.filter(status='present').count()
        
        if total_classes > 0:
            attendance_percentage = (present_classes / total_classes) * 100
            
            if attendance_percentage < threshold:
                low_attendance_students.append({
                    'student_id': student.student_id,
                    'name': student.user.full_name,
                    'roll_number': student.roll_number,
                    'class': student.class_section.section_name if student.class_section else 'N/A',
                    'department': student.department.department_name,
                    'semester': student.current_semester,
                    'attendance_percentage': round(attendance_percentage, 2),
                    'total_classes': total_classes,
                    'present_classes': present_classes,
                    'absent_classes': total_classes - present_classes
                })
    
    # Sort by attendance percentage (ascending)
    low_attendance_students.sort(key=lambda x: x['attendance_percentage'])
    
    # Get counts for dashboard
    total_students = students.count()
    warning_count = len([s for s in low_attendance_students if s['attendance_percentage'] >= 65 and s['attendance_percentage'] < 75])
    critical_count = len([s for s in low_attendance_students if s['attendance_percentage'] < 65])
    good_count = total_students - warning_count - critical_count
    
    # Calculate percentages
    warning_percentage = (warning_count / total_students * 100) if total_students > 0 else 0
    critical_percentage = (critical_count / total_students * 100) if total_students > 0 else 0
    good_percentage = (good_count / total_students * 100) if total_students > 0 else 0
    
    # Paginate results
    paginator = Paginator(low_attendance_students, 10)  # 10 students per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'total_students': total_students,
        'warning_count': warning_count,
        'critical_count': critical_count,
        'good_count': good_count,
        'warning_percentage': round(warning_percentage, 1),
        'critical_percentage': round(critical_percentage, 1),
        'good_percentage': round(good_percentage, 1),
        'departments': departments,
        'subjects': subjects,
        'filter_form': filter_form,
        'low_attendance_students': page_obj,
        'lab_assistant': lab_assistant,
        'threshold': threshold
    }
    
    return render(request, 'lab_assistant_portal/low_attendance.html', context)

@login_required
@lab_assistant_required
def get_student_attendance_details(request):
    """AJAX endpoint to get detailed attendance for a student"""
    student_id = request.GET.get('student_id')
    logger.info(f"User {request.user.username} requested attendance details for student {student_id}")
    
    if not student_id:
        return JsonResponse({'success': False, 'message': 'Student ID is required'})
    
    try:
        student = Student.objects.get(student_id=student_id)
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Student not found'})
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant or student.department != lab_assistant.department:
        return JsonResponse({'success': False, 'message': 'You do not have permission to view this student\'s attendance'})
    
    # Get current academic year
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    
    # Get attendance records for student by subject
    subject_attendance = []
    
    # Get all subjects for the student's semester
    subjects = Subject.objects.filter(
        department=student.department,
        semester=student.current_semester
    )
    
    for subject in subjects:
        # Get attendance records for this subject
        attendance_records = Attendance.objects.filter(
            student=student,
            faculty_subject__subject=subject,
            status__in=['present', 'absent']
        )
        
        if current_academic_year:
            attendance_records = attendance_records.filter(
                faculty_subject__academic_year=current_academic_year
            )
        
        total_classes = attendance_records.count()
        present_classes = attendance_records.filter(status='present').count()
        
        if total_classes > 0:
            attendance_percentage = (present_classes / total_classes) * 100
            
            subject_attendance.append({
                'subject_name': subject.subject_name,
                'subject_code': subject.subject_code,
                'total_classes': total_classes,
                'present_classes': present_classes,
                'absent_classes': total_classes - present_classes,
                'attendance_percentage': round(attendance_percentage, 2)
            })
    
    # Sort by attendance percentage (ascending)
    subject_attendance.sort(key=lambda x: x['attendance_percentage'])
    
    # Get overall attendance
    total_overall = sum(item['total_classes'] for item in subject_attendance)
    present_overall = sum(item['present_classes'] for item in subject_attendance)
    
    overall_percentage = (present_overall / total_overall * 100) if total_overall > 0 else 0
    
    # Get recent attendance
    recent_attendance = Attendance.objects.filter(
        student=student
    ).order_by('-attendance_date')[:10]
    
    recent_records = []
    for record in recent_attendance:
        recent_records.append({
            'date': record.attendance_date.strftime('%Y-%m-%d'),
            'subject': record.faculty_subject.subject.subject_name,
            'status': record.status.title(),
            'recorded_by': record.recorded_by.user.full_name,
            'is_lab': record.faculty_subject.is_lab
        })
    
    # Prepare HTML response
    from django.template.loader import render_to_string
    html = render_to_string('lab_assistant_portal/partials/student_attendance_details.html', {
        'student': student,
        'subject_attendance': subject_attendance,
        'overall_percentage': round(overall_percentage, 2),
        'recent_attendance': recent_records
    })
    
    response_data = {
        'success': True,
        'data': {
            'student_name': student.user.full_name,
            'roll_number': student.roll_number,
            'department': student.department.department_name,
            'semester': student.current_semester,
            'attendance_percentage': round(overall_percentage, 2)
        },
        'html': html
    }
    
    return JsonResponse(response_data)

@login_required
@lab_assistant_required
def notify_student(request, student_id):
    """Notify a student about their low attendance"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
            return redirect('/')
        
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            messages.error(request, "Student not found.")
            return redirect('lab_assistant_portal:low_attendance')
        
        # Check if lab assistant has permission
        if student.department != lab_assistant.department:
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to notify this student.',
                'return_url': reverse('lab_assistant_portal:low_attendance')
            })
        
        # Get notification message
        message = request.POST.get('message', '')
        
        # In a real implementation, you would send an email or create a notification in the system
        # For now, we'll just log the action
        
        log_action(
            user=user,
            action=f"Sent low attendance notification to student {student.user.full_name}",
            details=f"Notification: {message}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} sent a notification to student {student_id}")
        messages.success(request, "Notification sent successfully.")
    
    return redirect('lab_assistant_portal:low_attendance')

@login_required
@lab_assistant_required
def lab_schedule(request):
    """View for lab schedule"""
    logger.info(f"User {request.user.username} accessed lab schedule")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
        return redirect('/')
    
    # Get current academic year
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    
    # Get all labs (subjects with has_lab=True)
    labs = Subject.objects.filter(
        department=lab_assistant.department,
        has_lab=True
    ).order_by('subject_name')
    
    # Get all batches
    batches = Batch.objects.all().order_by('batch_name')
    
    # Define time slots
    time_slots = [
        {'start': '09:00', 'end': '10:00'},
        {'start': '10:00', 'end': '11:00'},
        {'start': '11:00', 'end': '12:00'},
        {'start': '12:00', 'end': '13:00'},
        {'start': '13:00', 'end': '14:00'},
        {'start': '14:00', 'end': '15:00'},
        {'start': '15:00', 'end': '16:00'},
        {'start': '16:00', 'end': '17:00'},
    ]
    
    # Define breaks
    breaks = [
        {'start': '12:00', 'end': '13:00', 'name': 'Lunch Break'}
    ]
    
    # Get lab sessions from timetable
    weekly_schedule = {
        'Monday': [],
        'Tuesday': [],
        'Wednesday': [],
        'Thursday': [],
        'Friday': [],
        'Saturday': []
    }
    
    from django.db import connections
    cursor = connections['default'].cursor()
    
    for day in weekly_schedule.keys():
        # Execute a raw SQL query to get timetable for the day
        cursor.execute('''
            SELECT t.timetable_id, t.start_time, t.end_time, t.room_number, 
                   s.subject_name, s.subject_id, u.full_name as faculty_name, f.faculty_id,
                   b.batch_name, cs.section_name, cs.class_section_id
            FROM timetable t
            JOIN faculty_subject fs ON t.faculty_subject_id = fs.faculty_subject_id
            JOIN subjects s ON fs.subject_id = s.subject_id
            JOIN faculty f ON fs.faculty_id = f.faculty_id
            JOIN users u ON f.user_id = u.user_id
            LEFT JOIN batches b ON fs.batch_id = b.batch_id
            LEFT JOIN class_sections cs ON fs.class_section_id = cs.class_section_id
            WHERE fs.is_lab = TRUE
            AND t.day_of_week = %s
            AND fs.academic_year_id = %s
            AND EXISTS (
                SELECT 1 FROM class_sections cs2
                WHERE cs2.class_section_id = fs.class_section_id
                AND cs2.department_id = %s
            )
            ORDER BY t.start_time
        ''', [day, current_academic_year.academic_year_id if current_academic_year else 0, lab_assistant.department.department_id])
        
        for row in cursor.fetchall():
            timetable_id, start_time, end_time, room_number, subject_name, subject_id, faculty_name, faculty_id, batch_name, section_name, class_section_id = row
            weekly_schedule[day].append({
                'session_id': timetable_id,
                'start_time': start_time.strftime('%H:%M') if hasattr(start_time, 'strftime') else start_time,
                'end_time': end_time.strftime('%H:%M') if hasattr(end_time, 'strftime') else end_time,
                'room': room_number,
                'subject': subject_name,
                'subject_id': subject_id,
                'faculty': faculty_name,
                'faculty_id': faculty_id,
                'batch': batch_name,
                'section': section_name,
                'class_section_id': class_section_id
            })
    
    # Get lab issues
    lab_issues = LabIssue.objects.filter(
        status__in=['open', 'in_progress'],
        reported_by__department=lab_assistant.department
    ).select_related('reported_by', 'reported_by__user').order_by('-priority', '-reported_at')[:5]
    
    # Get equipment status (mocked for now)
    equipment_status = [
        {'name': 'Computer Lab 1', 'status': 'operational', 'last_checked': timezone.now().date() - timedelta(days=2)},
        {'name': 'Computer Lab 2', 'status': 'operational', 'last_checked': timezone.now().date() - timedelta(days=1)},
        {'name': 'Electronics Lab', 'status': 'issues', 'last_checked': timezone.now().date() - timedelta(days=3)},
        {'name': 'Networking Lab', 'status': 'operational', 'last_checked': timezone.now().date()}
    ]
    
    context = {
        'labs': labs,
        'batches': batches,
        'weekly_schedule': {
            'days': weekly_schedule,
            'time_slots': time_slots,
            'breaks': breaks
        },
        'lab_issues': lab_issues,
        'equipment_status': equipment_status,
        'lab_assistant': lab_assistant
    }
    
    return render(request, 'lab_assistant_portal/lab_schedule.html', context)

@login_required
@lab_assistant_required
def get_session_details(request):
    """AJAX endpoint to get lab session details"""
    session_id = request.GET.get('session_id')
    logger.info(f"User {request.user.username} requested details for lab session {session_id}")
    
    if not session_id:
        return JsonResponse({'success': False, 'message': 'Session ID is required'})
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
    
    try:
        # Execute a raw SQL query to get session details
        from django.db import connections
        cursor = connections['default'].cursor()
        
        cursor.execute('''
            SELECT t.start_time, t.end_time, t.room_number, t.day_of_week,
                   s.subject_name, u.full_name as faculty_name,
                   b.batch_name, cs.section_name
            FROM timetable t
            JOIN faculty_subject fs ON t.faculty_subject_id = fs.faculty_subject_id
            JOIN subjects s ON fs.subject_id = s.subject_id
            JOIN faculty f ON fs.faculty_id = f.faculty_id
            JOIN users u ON f.user_id = u.user_id
            LEFT JOIN batches b ON fs.batch_id = b.batch_id
            LEFT JOIN class_sections cs ON fs.class_section_id = cs.class_section_id
            WHERE t.timetable_id = %s
        ''', [session_id])
        
        row = cursor.fetchone()
        
        if not row:
            return JsonResponse({'success': False, 'message': 'Session not found'})
        
        start_time, end_time, room_number, day_of_week, subject_name, faculty_name, batch_name, section_name = row
        
        # Prepare HTML response
        from django.template.loader import render_to_string
        html = render_to_string('lab_assistant_portal/partials/session_details.html', {
            'session': {
                'subject_name': subject_name,
                'faculty_name': faculty_name,
                'batch_name': batch_name or 'All',
                'section_name': section_name or 'All',
                'room_number': room_number,
                'day_of_week': day_of_week,
                'start_time': start_time.strftime('%H:%M') if hasattr(start_time, 'strftime') else start_time,
                'end_time': end_time.strftime('%H:%M') if hasattr(end_time, 'strftime') else end_time
            }
        })
        
        response_data = {
            'success': True,
            'data': {
                'subject_name': subject_name,
                'faculty_name': faculty_name,
                'batch_name': batch_name or 'All',
                'lab_name': room_number,
                'day_of_week': day_of_week,
                'start_time': start_time.strftime('%H:%M') if hasattr(start_time, 'strftime') else start_time,
                'end_time': end_time.strftime('%H:%M') if hasattr(end_time, 'strftime') else end_time
            },
            'html': html
        }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        logger.error(f"Error getting session details: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

@login_required
@lab_assistant_required
def get_session_attendance(request):
    """AJAX endpoint to get attendance for a lab session"""
    session_id = request.GET.get('session_id')
    date_str = request.GET.get('date')
    logger.info(f"User {request.user.username} requested attendance for lab session {session_id} on {date_str}")
    
    if not session_id:
        return JsonResponse({'success': False, 'message': 'Session ID is required'})
    
    if not date_str:
        date_str = timezone.now().date().strftime('%Y-%m-%d')
    
    try:
        session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format'})
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
    
    try:
        # Get timetable entry
        from django.db import connections
        cursor = connections['default'].cursor()
        
        cursor.execute('''
            SELECT t.faculty_subject_id, s.subject_name, fs.is_lab
            FROM timetable t
            JOIN faculty_subject fs ON t.faculty_subject_id = fs.faculty_subject_id
            JOIN subjects s ON fs.subject_id = s.subject_id
            WHERE t.timetable_id = %s
        ''', [session_id])
        
        row = cursor.fetchone()
        
        if not row:
            return JsonResponse({'success': False, 'message': 'Session not found'})
        
        faculty_subject_id, subject_name, is_lab = row
        
        if not is_lab:
            return JsonResponse({'success': False, 'message': 'This is not a lab session'})
        
        # Get attendance for this session and date
        attendance_records = Attendance.objects.filter(
            faculty_subject_id=faculty_subject_id,
            attendance_date=session_date
        ).select_related('student', 'student__user')
        
        total_students = attendance_records.count()
        present_count = attendance_records.filter(status='present').count()
        absent_count = attendance_records.filter(status='absent').count()
        
        # Prepare student attendance list
        students_attendance = []
        for record in attendance_records:
            students_attendance.append({
                'student_id': record.student.student_id,
                'name': record.student.user.full_name,
                'roll_number': record.student.roll_number,
                'status': record.status
            })
        
        # Sort by roll number
        students_attendance.sort(key=lambda x: x['roll_number'])
        
        # Prepare HTML response
        from django.template.loader import render_to_string
        html = render_to_string('lab_assistant_portal/partials/session_attendance.html', {
            'subject_name': subject_name,
            'date': session_date,
            'total_students': total_students,
            'present_count': present_count,
            'absent_count': absent_count,
            'students': students_attendance
        })
        
        response_data = {
            'success': True,
            'data': {
                'subject_name': subject_name,
                'date': session_date.strftime('%Y-%m-%d'),
                'present_count': present_count,
                'absent_count': absent_count,
                'total_students': total_students
            },
            'html': html
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"Error getting session attendance: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

@login_required
@lab_assistant_required
def report_lab_issue(request):
    """Report an issue with a lab"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        form = LabIssueForm(request.POST)
        
        if form.is_valid():
            issue = form.save(commit=False)
            issue.reported_by = lab_assistant
            issue.save()
            
            # Log the action
            log_action(
                user=user,
                action=f"Reported lab issue: {issue.issue_type} in {issue.lab_name}",
                details=f"Description: {issue.description}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} reported a lab issue")
            return JsonResponse({
                'success': True,
                'message': 'Issue reported successfully',
                'issue': {
                    'id': issue.issue_id,
                    'lab_name': issue.lab_name,
                    'issue_type': issue.get_issue_type_display(),
                    'priority': issue.get_priority_display(),
                    'status': issue.get_status_display(),
                    'reported_at': issue.reported_at.strftime('%Y-%m-%d %H:%M')
                }
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid form data', 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def mark_issue_resolved(request):
    """Mark a lab issue as resolved"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        issue_id = request.POST.get('issue_id')
        resolution_notes = request.POST.get('resolution_notes', '')
        
        if not issue_id:
            return JsonResponse({'success': False, 'message': 'Issue ID is required'})
        
        try:
            issue = LabIssue.objects.get(issue_id=issue_id)
        except LabIssue.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Issue not found'})
        
        # Check if lab assistant has permission
        if issue.reported_by.department != lab_assistant.department:
            return JsonResponse({'success': False, 'message': 'You do not have permission to resolve this issue'})
        
        # Update issue
        issue.status = 'resolved'
        issue.resolved_by = lab_assistant
        issue.resolved_at = timezone.now()
        issue.resolution_notes = resolution_notes
        issue.save()
        
        # Log the action
        log_action(
            user=user,
            action=f"Resolved lab issue #{issue_id}",
            details=f"Resolution: {resolution_notes}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} marked lab issue {issue_id} as resolved")
        return JsonResponse({'success': True, 'message': 'Issue marked as resolved'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def reports(request):
    """View for generating reports"""
    logger.info(f"User {request.user.username} accessed reports")
    
    user = request.user
    lab_assistant = get_lab_assistant(user)
    
    if not lab_assistant:
        messages.error(request, "Lab Assistant profile not found. Please contact the administrator.")
        return redirect('/')
    
    # Get all departments
    departments = Department.objects.all()
    
    # Get labs (subjects with has_lab=True)
    labs = Subject.objects.filter(
        department=lab_assistant.department,
        has_lab=True
    ).order_by('subject_name')
    
    # Get batches
    batches = Batch.objects.all().order_by('batch_name')
    
    # Get subjects for this department
    subjects = Subject.objects.filter(
        department=lab_assistant.department
    ).order_by('subject_name')
    
    # Create report generation form
    form = ReportGenerationForm(departments=departments)
    
    # Get recent generated reports (mock data for now)
    recent_reports = [
        {
            'id': 1,
            'name': 'Monthly Attendance Report - March 2025',
            'type': 'Attendance',
            'generated_at': timezone.now() - timedelta(days=3),
            'format': 'PDF',
            'size': '1.2 MB'
        },
        {
            'id': 2,
            'name': 'Leave Applications Summary - Q1 2025',
            'type': 'Leave',
            'generated_at': timezone.now() - timedelta(days=7),
            'format': 'Excel',
            'size': '425 KB'
        },
        {
            'id': 3,
            'name': 'Low Attendance Alert - Week 12',
            'type': 'Low Attendance',
            'generated_at': timezone.now() - timedelta(days=2),
            'format': 'PDF',
            'size': '890 KB'
        }
    ]
    
    # Get scheduled reports
    scheduled_reports = ScheduledReport.objects.filter(
        created_by=lab_assistant
    ).order_by('next_run')
    
    context = {
        'departments': departments,
        'labs': labs,
        'batches': batches,
        'subjects': subjects,
        'form': form,
        'recent_reports': recent_reports,
        'scheduled_reports': scheduled_reports,
        'lab_assistant': lab_assistant
    }
    
    return render(request, 'lab_assistant_portal/reports.html', context)

@login_required
@lab_assistant_required
def generate_report(request):
    """Generate a new report"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        # Get all departments
        departments = Department.objects.all()
        
        # Process form
        form = ReportGenerationForm(request.POST, departments=departments)
        
        if form.is_valid():
            report_type = form.cleaned_data.get('report_type')
            department_id = form.cleaned_data.get('department')
            from_date = form.cleaned_data.get('from_date')
            to_date = form.cleaned_data.get('to_date')
            report_format = form.cleaned_data.get('format')
            include_charts = form.cleaned_data.get('include_charts')
            
            # Log the report generation
            log_action(
                user=user,
                action=f"Generated {report_type} report",
                details=f"Date range: {from_date} to {to_date}, Format: {report_format}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} generated a {report_type} report")
            
            # In a real implementation, you would generate the actual report here
            # For now, we'll just return a success response with mock data
            
            # Create HTML report preview based on report type
            if report_type == 'attendance':
                # Generate attendance report
                from django.template.loader import render_to_string
                
                # Get attendance data by department
                attendance_data = []
                
                if department_id:
                    department = Department.objects.get(department_id=department_id)
                    department_filter = Q(student__department_id=department_id)
                    department_name = department.department_name
                else:
                    department_filter = Q(student__department=lab_assistant.department)
                    department_name = lab_assistant.department.department_name
                
                # Get attendance records for date range
                attendance_records = Attendance.objects.filter(
                    department_filter,
                    attendance_date__gte=from_date,
                    attendance_date__lte=to_date
                )
                
                # Group by subject
                subjects = Subject.objects.filter(
                    faculty_subject__attendance__in=attendance_records
                ).distinct()
                
                for subject in subjects:
                    subject_records = attendance_records.filter(
                        faculty_subject__subject=subject
                    )
                    
                    total_classes = subject_records.count()
                    present_count = subject_records.filter(status='present').count()
                    absent_count = subject_records.filter(status='absent').count()
                    dont_care_count = subject_records.filter(status='dont_care').count()
                    
                    if total_classes > 0:
                        attendance_percentage = (present_count / (present_count + absent_count)) * 100 if (present_count + absent_count) > 0 else 0
                        
                        attendance_data.append({
                            'subject_name': subject.subject_name,
                            'subject_code': subject.subject_code,
                            'total_classes': total_classes,
                            'present_count': present_count,
                            'absent_count': absent_count,
                            'dont_care_count': dont_care_count,
                            'attendance_percentage': round(attendance_percentage, 2)
                        })
                
                html = render_to_string('lab_assistant_portal/reports/attendance_report.html', {
                    'department_name': department_name,
                    'from_date': from_date,
                    'to_date': to_date,
                    'attendance_data': attendance_data
                })
                
                # Chart data for attendance percentages
                chart_data = {
                    'labels': [item['subject_name'] for item in attendance_data],
                    'attendance': [item['attendance_percentage'] for item in attendance_data]
                }
                
            elif report_type == 'leave':
                # Generate leave applications report
                from django.template.loader import render_to_string
                
                # Get leave data
                if department_id:
                    department = Department.objects.get(department_id=department_id)
                    leave_applications = LeaveApplication.objects.filter(
                        student__department_id=department_id,
                        start_date__gte=from_date,
                        end_date__lte=to_date
                    )
                    department_name = department.department_name
                else:
                    leave_applications = LeaveApplication.objects.filter(
                        student__department=lab_assistant.department,
                        start_date__gte=from_date,
                        end_date__lte=to_date
                    )
                    department_name = lab_assistant.department.department_name
                
                # Group by status
                pending_count = leave_applications.filter(status='pending').count()
                faculty_approved_count = leave_applications.filter(status='faculty_approved').count()
                lab_approved_count = leave_applications.filter(status='lab_approved').count()
                rejected_count = leave_applications.filter(status='rejected').count()
                
                # Group by month
                leave_by_month = {}
                for app in leave_applications:
                    month = app.start_date.strftime('%Y-%m')
                    leave_by_month[month] = leave_by_month.get(month, 0) + 1
                
                html = render_to_string('lab_assistant_portal/reports/leave_report.html', {
                    'department_name': department_name,
                    'from_date': from_date,
                    'to_date': to_date,
                    'leave_applications': leave_applications,
                    'pending_count': pending_count,
                    'faculty_approved_count': faculty_approved_count,
                    'lab_approved_count': lab_approved_count,
                    'rejected_count': rejected_count,
                    'total_count': leave_applications.count()
                })
                
                # Chart data for status distribution
                chart_data = {
                    'labels': ['Pending', 'Faculty Approved', 'Lab Approved', 'Rejected'],
                    'counts': [pending_count, faculty_approved_count, lab_approved_count, rejected_count],
                    'leave_by_month': {
                        'labels': list(leave_by_month.keys()),
                        'counts': list(leave_by_month.values())
                    }
                }
                
            elif report_type == 'lab_usage':
                # Generate lab usage report
                from django.template.loader import render_to_string
                
                # Get lab sessions from timetable
                lab_sessions = FacultySubject.objects.filter(
                    is_lab=True,
                    class_section__department=lab_assistant.department
                ).count()
                
                # Get attendance for lab sessions
                lab_attendance = Attendance.objects.filter(
                    faculty_subject__is_lab=True,
                    student__department=lab_assistant.department,
                    attendance_date__gte=from_date,
                    attendance_date__lte=to_date
                )
                
                # Group by lab (room)
                labs_usage = {}
                for record in lab_attendance:
                    # Get timetable entry for this attendance
                    from django.db import connections
                    cursor = connections['default'].cursor()
                    
                    cursor.execute('''
                        SELECT t.room_number
                        FROM timetable t
                        WHERE t.faculty_subject_id = %s
                        LIMIT 1
                    ''', [record.faculty_subject_id])
                    
                    row = cursor.fetchone()
                    if row:
                        room = row[0]
                        labs_usage[room] = labs_usage.get(room, 0) + 1
                
                html = render_to_string('lab_assistant_portal/reports/lab_usage_report.html', {
                    'department_name': lab_assistant.department.department_name,
                    'from_date': from_date,
                    'to_date': to_date,
                    'lab_sessions': lab_sessions,
                    'labs_usage': labs_usage
                })
                
                # Chart data for lab usage
                chart_data = {
                    'labels': list(labs_usage.keys()),
                    'counts': list(labs_usage.values())
                }
                
            elif report_type == 'low_attendance':
                # Generate low attendance report
                from django.template.loader import render_to_string
                
                # Get students with attendance below 75%
                low_attendance_students = []
                threshold = 75
                
                if department_id:
                    department = Department.objects.get(department_id=department_id)
                    students = Student.objects.filter(
                        department_id=department_id,
                        status='active'
                    )
                    department_name = department.department_name
                else:
                    students = Student.objects.filter(
                        department=lab_assistant.department,
                        status='active'
                    )
                    department_name = lab_assistant.department.department_name
                
                for student in students:
                    # Get attendance records for date range
                    attendance_records = Attendance.objects.filter(
                        student=student,
                        attendance_date__gte=from_date,
                        attendance_date__lte=to_date,
                        status__in=['present', 'absent']
                    )
                    
                    if attendance_records.exists():
                        total_classes = attendance_records.count()
                        present_classes = attendance_records.filter(status='present').count()
                        
                        attendance_percentage = (present_classes / total_classes) * 100 if total_classes > 0 else 100
                        
                        if attendance_percentage < threshold:
                            low_attendance_students.append({
                                'student_id': student.student_id,
                                'name': student.user.full_name,
                                'roll_number': student.roll_number,
                                'semester': student.current_semester,
                                'attendance_percentage': round(attendance_percentage, 2),
                                'total_classes': total_classes,
                                'present_classes': present_classes,
                                'absent_classes': total_classes - present_classes
                            })
                
                # Group by attendance range
                critical_count = len([s for s in low_attendance_students if s['attendance_percentage'] < 65])
                warning_count = len([s for s in low_attendance_students if s['attendance_percentage'] >= 65 and s['attendance_percentage'] < 75])
                
                html = render_to_string('lab_assistant_portal/reports/low_attendance_report.html', {
                    'department_name': department_name,
                    'from_date': from_date,
                    'to_date': to_date,
                    'threshold': threshold,
                    'low_attendance_students': low_attendance_students,
                    'critical_count': critical_count,
                    'warning_count': warning_count,
                    'total_count': len(low_attendance_students)
                })
                
                # Chart data for attendance distribution
                chart_data = {
                    'labels': ['Critical (<65%)', 'Warning (65-75%)'],
                    'counts': [critical_count, warning_count]
                }
            
            return JsonResponse({
                'success': True,
                'html': html,
                'charts': chart_data if include_charts else {},
                'report_info': {
                    'type': report_type,
                    'department': department_name,
                    'from_date': from_date.strftime('%Y-%m-%d'),
                    'to_date': to_date.strftime('%Y-%m-%d'),
                    'format': report_format,
                    'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid form data', 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def view_report(request):
    """View a previously generated report"""
    report_id = request.GET.get('report_id')
    logger.info(f"User {request.user.username} viewed report {report_id}")
    
    if not report_id:
        return JsonResponse({'success': False, 'message': 'Report ID is required'})
    
    # In a real implementation, you would retrieve the report from the database
    # For now, we'll just return a mock response
    
    response_data = {
        'success': True,
        'html': '<div class="alert alert-info">This report would be retrieved from the database in a real implementation.</div>',
        'charts': {}
    }
    
    return JsonResponse(response_data)

@login_required
@lab_assistant_required
def schedule_report(request):
    """Schedule a report for automatic generation"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        # Get all departments
        departments = Department.objects.all()
        
        # Get all subjects
        subjects = Subject.objects.filter(department=lab_assistant.department)
        
        # Get all batches
        batches = Batch.objects.all()
        
        # Process form
        form = ScheduledReportForm(
            request.POST,
            departments=departments,
            subjects=subjects,
            batches=batches
        )
        
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = lab_assistant
            
            # Set next run based on frequency
            if report.frequency == 'daily':
                report.next_run = timezone.now() + timedelta(days=1)
            elif report.frequency == 'weekly':
                report.next_run = timezone.now() + timedelta(days=7)
            elif report.frequency == 'monthly':
                report.next_run = timezone.now() + timedelta(days=30)
            
            # Additional filters
            filters = {
                'department': form.cleaned_data.get('department'),
                'batch': form.cleaned_data.get('batch'),
                'subject': form.cleaned_data.get('subject')
            }
            
            report.filters = json.dumps(filters)
            report.save()
            
            # Log the action
            log_action(
                user=user,
                action=f"Scheduled {report.report_type} report",
                details=f"Name: {report.name}, Frequency: {report.frequency}, Next run: {report.next_run}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} scheduled a new report")
            return JsonResponse({
                'success': True,
                'message': 'Report scheduled successfully',
                'report': {
                    'id': report.report_id,
                    'name': report.name,
                    'type': report.get_report_type_display(),
                    'frequency': report.get_frequency_display(),
                    'next_run': report.next_run.strftime('%Y-%m-%d %H:%M'),
                    'format': report.get_format_display(),
                    'status': report.get_status_display()
                }
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid form data', 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def share_report(request):
    """Share a report with others"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        report_id = request.POST.get('report_id')
        recipients = request.POST.get('recipients', '')
        
        if not report_id:
            return JsonResponse({'success': False, 'message': 'Report ID is required'})
        
        # Validate recipients (comma-separated email addresses)
        email_list = [email.strip() for email in recipients.split(',') if email.strip()]
        
        for email in email_list:
            if not email.endswith('@mbit.edu.in'):
                return JsonResponse({'success': False, 'message': f'Invalid email address: {email}'})
        
        # In a real implementation, you would send emails or create notifications
        # For now, we'll just log the action
        
        log_action(
            user=user,
            action=f"Shared report #{report_id}",
            details=f"Recipients: {recipients}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} shared report {report_id}")
        return JsonResponse({'success': True, 'message': 'Report shared successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def get_scheduled_report_details(request):
    """AJAX endpoint to get details of a scheduled report"""
    report_id = request.GET.get('report_id')
    logger.info(f"User {request.user.username} requested details for scheduled report {report_id}")
    
    if not report_id:
        return JsonResponse({'success': False, 'message': 'Report ID is required'})
    
    try:
        report = ScheduledReport.objects.get(report_id=report_id)
    except ScheduledReport.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Report not found'})
    
    # Get filters
    filters = {}
    if report.filters:
        try:
            filters = json.loads(report.filters)
        except:
            filters = {}
    
    # Get department name if applicable
    department_name = ''
    if filters.get('department'):
        try:
            department = Department.objects.get(department_id=filters['department'])
            department_name = department.department_name
        except Department.DoesNotExist:
            department_name = 'Unknown'
    
    filter_text = []
    if department_name:
        filter_text.append(f"Department: {department_name}")
    
    if filters.get('batch'):
        try:
            batch = Batch.objects.get(batch_id=filters['batch'])
            filter_text.append(f"Batch: {batch.batch_name}")
        except Batch.DoesNotExist:
            pass
    
    if filters.get('subject'):
        try:
            subject = Subject.objects.get(subject_id=filters['subject'])
            filter_text.append(f"Subject: {subject.subject_name}")
        except Subject.DoesNotExist:
            pass
    
    response_data = {
        'success': True,
        'data': {
            'name': report.name,
            'type': report.get_report_type_display(),
            'frequency': report.get_frequency_display(),
            'next_run': report.next_run.strftime('%Y-%m-%d %H:%M') if report.next_run else 'Not scheduled',
            'recipients': report.recipients,
            'format': report.get_format_display(),
            'status': report.get_status_display(),
            'filters': ', '.join(filter_text) if filter_text else 'None'
        }
    }
    
    return JsonResponse(response_data)

@login_required
@lab_assistant_required
def delete_scheduled_report(request):
    """Delete a scheduled report"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        report_id = request.POST.get('report_id')
        
        if not report_id:
            return JsonResponse({'success': False, 'message': 'Report ID is required'})
        
        try:
            report = ScheduledReport.objects.get(report_id=report_id)
        except ScheduledReport.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Report not found'})
        
        # Check if lab assistant has permission
        if report.created_by != lab_assistant:
            return JsonResponse({'success': False, 'message': 'You do not have permission to delete this report'})
        
        # Delete report
        report_name = report.name
        report.delete()
        
        # Log the action
        log_action(
            user=user,
            action=f"Deleted scheduled report",
            details=f"Report: {report_name}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} deleted scheduled report {report_id}")
        return JsonResponse({'success': True, 'message': 'Report deleted successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def update_profile(request):
    """Update lab assistant profile"""
    if request.method == 'POST':
        user = request.user
        lab_assistant = get_lab_assistant(user)
        
        if not lab_assistant:
            return JsonResponse({'success': False, 'message': 'Lab assistant profile not found'})
        
        form = ProfileUpdateForm(request.POST)
        
        if form.is_valid():
            # Update user info
            user.full_name = form.cleaned_data['full_name']
            
            # Check if email is being changed
            new_email = form.cleaned_data['email']
            if new_email != user.email:
                # Check if email is unique
                if User.objects.filter(email=new_email).exclude(user_id=user.user_id).exists():
                    return JsonResponse({'success': False, 'message': 'Email address is already in use'})
                
                user.email = new_email
            
            user.save()
            
            # Update lab assistant info
            lab_assistant.dob = form.cleaned_data['dob']
            lab_assistant.joining_year = form.cleaned_data['joining_year']
            lab_assistant.save()
            
            # Log the action
            log_action(
                user=user,
                action="Updated profile",
                details="Updated personal information",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} updated their profile")
            return JsonResponse({'success': True, 'message': 'Profile updated successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid form data', 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def change_password(request):
    """Change lab assistant password"""
    if request.method == 'POST':
        user = request.user
        
        form = PasswordChangeForm(request.POST)
        
        if form.is_valid():
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']
            
            # Check if current password is correct
            if not check_password(current_password, user.password):
                return JsonResponse({'success': False, 'message': 'Current password is incorrect'})
            
            # Update password
            user.password = make_password(new_password)
            user.save()
            
            # Log the action
            log_action(
                user=user,
                action="Changed password",
                details="Password updated",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} changed their password")
            return JsonResponse({'success': True, 'message': 'Password changed successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid form data', 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def update_profile_photo(request):
    """Update lab assistant profile photo"""
    if request.method == 'POST':
        user = request.user
        
        if 'photo' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No photo uploaded'})
        
        photo = request.FILES['photo']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif']
        if photo.content_type not in allowed_types:
            return JsonResponse({'success': False, 'message': 'Invalid file type. Only JPEG, PNG, and GIF are allowed'})
        
        # Validate file size (max 2MB)
        if photo.size > 2 * 1024 * 1024:
            return JsonResponse({'success': False, 'message': 'File size exceeds 2MB limit'})
        
        # In a real implementation, you would save the file and update the user's profile
        # For now, we'll just log the action
        
        log_action(
            user=user,
            action="Updated profile photo",
            details=f"File: {photo.name}, Size: {photo.size} bytes",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} updated their profile photo")
        return JsonResponse({'success': True, 'message': 'Profile photo updated successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def remove_profile_photo(request):
    """Remove lab assistant profile photo"""
    if request.method == 'POST':
        user = request.user
        
        # In a real implementation, you would remove the file and update the user's profile
        # For now, we'll just log the action
        
        log_action(
            user=user,
            action="Removed profile photo",
            details="Profile photo removed",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        logger.info(f"User {request.user.username} removed their profile photo")
        return JsonResponse({'success': True, 'message': 'Profile photo removed successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
def update_notification_settings(request):
    """Update notification settings"""
    if request.method == 'POST':
        user = request.user
        
        form = NotificationSettingsForm(request.POST)
        
        if form.is_valid():
            # In a real implementation, you would save these settings to the database
            # For now, we'll just log the action
            
            settings_data = {
                'email_leave_applications': form.cleaned_data['email_leave_applications'],
                'email_attendance_exceptions': form.cleaned_data['email_attendance_exceptions'],
                'email_low_attendance': form.cleaned_data['email_low_attendance'],
                'portal_leave_applications': form.cleaned_data['portal_leave_applications'],
                'portal_attendance_exceptions': form.cleaned_data['portal_attendance_exceptions'],
                'portal_low_attendance': form.cleaned_data['portal_low_attendance']
            }
            
            log_action(
                user=user,
                action="Updated notification settings",
                details=f"Settings: {json.dumps(settings_data)}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            logger.info(f"User {request.user.username} updated their notification settings")
            return JsonResponse({'success': True, 'message': 'Notification settings updated successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Invalid form data', 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@lab_assistant_required
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