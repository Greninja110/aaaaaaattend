from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Case, When, IntegerField, F, Q, Avg
from django.core.paginator import Paginator
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from authentication.models import User, Role
from core.models import Student, Department, Faculty, AcademicYear, ClassSection, Batch
# Update any imports of Attendance, LeaveApplication to import from core
from core.models import Attendance, LeaveApplication, FacultySubject, Subject , Timetable
from .models import Attendance, LeaveApplication, Notification, StudentProfile, UserPreference, NotificationSetting, AttendanceCorrectionRequest
import json
import logging
import os
import datetime
import calendar
import uuid
import pandas as pd
import io
import csv
from dateutil.relativedelta import relativedelta
from django.db import models

# Configure logging
logger = logging.getLogger(__name__)
log_file = os.path.join(os.path.dirname(__file__), 'student_portal.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)
file_handler = logging.FileHandler(log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)



# Helper functions
def get_student_for_user(user):
    """Get student object associated with user"""
    try:
        return Student.objects.get(user=user)
    except Student.DoesNotExist:
        logger.error(f"Student record not found for user {user.username}")
        return None

def get_current_academic_year():
    """Get current academic year"""
    try:
        return AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        # Fallback to create one if none is set as current
        current_year = timezone.now().year
        academic_year, created = AcademicYear.objects.get_or_create(
            year_start=current_year,
            year_end=current_year + 1,
            defaults={'is_current': True}
        )
        return academic_year

def get_student_subjects(student, academic_year=None):
    """Get subjects for a student in the current semester"""
    if not academic_year:
        academic_year = get_current_academic_year()
        
    # This would typically come from student_subject table
    # For now, we'll get all subjects for the student's current semester and department
    return Subject.objects.filter(
        department=student.department,
        semester=student.current_semester
    )

def get_attendance_percentage(student, subject=None, academic_year=None):
    """Calculate attendance percentage for a student"""
    if not academic_year:
        academic_year = get_current_academic_year()
        
    # Get faculty_subject entries
    faculty_subjects = FacultySubject.objects.filter(
        academic_year=academic_year
    )
    
    if subject:
        faculty_subjects = faculty_subjects.filter(subject=subject)
    else:
        subject_ids = get_student_subjects(student, academic_year).values_list('subject_id', flat=True)
        faculty_subjects = faculty_subjects.filter(subject_id__in=subject_ids)
    
    # Query attendance for these faculty_subjects
    attendance_records = Attendance.objects.filter(
        student=student,
        faculty_subject__in=faculty_subjects,
        status__in=['present', 'absent']  # Exclude 'dont_care'
    )
    
    total_classes = attendance_records.count()
    if total_classes == 0:
        return 0
        
    classes_attended = attendance_records.filter(status='present').count()
    return round((classes_attended / total_classes) * 100, 2)

def get_subject_attendance(student, subject, academic_year=None):
    """Get detailed attendance for a specific subject"""
    if not academic_year:
        academic_year = get_current_academic_year()
        
    faculty_subjects = FacultySubject.objects.filter(
        subject=subject,
        academic_year=academic_year
    )
    
    attendance_records = Attendance.objects.filter(
        student=student,
        faculty_subject__in=faculty_subjects
    ).select_related('faculty_subject__faculty__user')
    
    total_classes = attendance_records.exclude(status='dont_care').count()
    present_count = attendance_records.filter(status='present').count()
    absent_count = attendance_records.filter(status='absent').count()
    leave_count = attendance_records.filter(status='leave').count()
    
    percentage = 0
    if total_classes > 0:
        percentage = round((present_count / total_classes) * 100, 2)
        
    return {
        'subject': subject,
        'total_classes': total_classes,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'attendance_percentage': percentage
    }

def get_monthly_attendance_data(student, months=6, subject=None):
    """Get monthly attendance data for charts"""
    # Get last N months
    end_date = timezone.now().date()
    start_date = end_date - relativedelta(months=months-1, day=1)
    
    # Generate month labels
    month_labels = []
    month_data = []
    
    current_date = start_date
    while current_date <= end_date:
        month_labels.append(current_date.strftime('%b %Y'))
        
        month_start = current_date.replace(day=1)
        if current_date.month == 12:
            month_end = current_date.replace(day=31)
        else:
            next_month = current_date.replace(month=current_date.month+1, day=1)
            month_end = next_month - datetime.timedelta(days=1)
            
        # Query for this month's attendance
        faculty_subjects = FacultySubject.objects.all()
        if subject:
            faculty_subjects = faculty_subjects.filter(subject=subject)
            
        attendance_records = Attendance.objects.filter(
            student=student,
            faculty_subject__in=faculty_subjects,
            attendance_date__gte=month_start,
            attendance_date__lte=month_end,
            status__in=['present', 'absent']  # Exclude 'dont_care'
        )
        
        total_classes = attendance_records.count()
        if total_classes > 0:
            classes_attended = attendance_records.filter(status='present').count()
            percentage = round((classes_attended / total_classes) * 100, 2)
        else:
            percentage = 0
            
        month_data.append(percentage)
        current_date = current_date + relativedelta(months=1)
        
    return {'months': month_labels, 'data': month_data}

def get_today_classes(student):
    """Get classes scheduled for today"""
    current_date = timezone.now().date()
    day_of_week = current_date.strftime('%A')
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get timetable entries for today's day of week
    timetable_entries = Timetable.objects.filter(
        day_of_week=day_of_week,
        academic_year=academic_year,
        faculty_subject__class_section=student.class_section
    ).select_related(
        'faculty_subject__subject',
        'faculty_subject__faculty__user'
    ).order_by('start_time')
    
    # For lab classes, filter by student's batch
    if student.batch:
        batch_entries = timetable_entries.filter(
            faculty_subject__batch=student.batch
        )
        
        # Combine theory and lab entries
        theory_entries = timetable_entries.filter(
            faculty_subject__is_lab=False
        )
        timetable_entries = theory_entries | batch_entries
    
    # Convert to list of dictionaries with formatted info
    current_time = timezone.now().time()
    
    classes = []
    for entry in timetable_entries:
        faculty_subject = entry.faculty_subject
        subject = faculty_subject.subject
        faculty = faculty_subject.faculty
        
        # Check if class has already happened today
        is_past = entry.end_time < current_time
        
        # For past classes, check if attended (would query from attendance table)
        attended = False
        if is_past:
            attended = Attendance.objects.filter(
                student=student,
                faculty_subject=faculty_subject,
                attendance_date=current_date,
                status='present'
            ).exists()
        
        class_info = {
            'subject_name': subject.subject_name,
            'subject_code': subject.subject_code,
            'faculty_name': faculty.user.full_name,
            'room_number': entry.room_number,
            'start_time': entry.start_time.strftime('%I:%M %p'),
            'end_time': entry.end_time.strftime('%I:%M %p'),
            'is_lab': faculty_subject.is_lab,
            'is_past': is_past,
            'attended': attended
        }
        classes.append(class_info)
    
    return classes

def get_recent_attendance(student, limit=5):
    """Get recent attendance records"""
    records = Attendance.objects.filter(
        student=student
    ).select_related(
        'faculty_subject__subject',
        'faculty_subject__faculty__user'
    ).order_by('-attendance_date')[:limit]
    
    recent_records = []
    for record in records:
        faculty_subject = record.faculty_subject
        subject = faculty_subject.subject
        faculty = faculty_subject.faculty
        
        record_info = {
            'date': record.attendance_date.strftime('%d %b, %Y'),
            'subject_name': subject.subject_name,
            'subject_code': subject.subject_code,
            'faculty_name': faculty.user.full_name,
            'start_time': '10:00 AM',  # Would come from timetable
            'end_time': '11:00 AM',    # Would come from timetable
            'status': record.status
        }
        recent_records.append(record_info)
    
    return recent_records

def get_student_notifications(student, limit=None, unread_only=False, category=None):
    """Get notifications for a student"""
    notifications = Notification.objects.filter(
        user=student.user
    ).order_by('-created_at')
    
    if unread_only:
        notifications = notifications.filter(is_read=False)
        
    if category:
        notifications = notifications.filter(category=category)
        
    if limit:
        notifications = notifications[:limit]
        
    return notifications

def get_leave_applications(student, status=None):
    """Get leave applications for a student"""
    applications = LeaveApplication.objects.filter(
        student=student
    ).order_by('-created_at')
    
    if status:
        applications = applications.filter(status=status)
        
    return applications

def calculate_leaves_taken(student, academic_year=None):
    """Calculate leaves taken in the current academic year"""
    if not academic_year:
        academic_year = get_current_academic_year()
    
    # Get approved leaves in academic year
    year_start = datetime.date(academic_year.year_start, 7, 1)  # Typically July 1
    year_end = datetime.date(academic_year.year_end, 6, 30)    # June 30 next year
    
    approved_leaves = LeaveApplication.objects.filter(
        student=student,
        status__in=['faculty_approved', 'lab_approved'],
        start_date__gte=year_start,
        end_date__lte=year_end
    )
    
    # Calculate total days
    total_days = 0
    for leave in approved_leaves:
        delta = leave.end_date - leave.start_date
        total_days += delta.days + 1  # +1 to include both start and end dates
    
    return total_days

# Dashboard view
@login_required
def index(request):
    """Student Dashboard view"""
    user = request.user
    
    # Check if user has student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_heading': 'Unauthorized Access',
            'error_message': 'You do not have permission to access the Student Portal.',
            'return_url': '/'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_heading': 'Student Record Not Found',
            'error_message': 'Your student profile could not be found. Please contact the administrator.',
            'return_url': '/'
        })
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get subjects for current semester
    subjects = get_student_subjects(student, academic_year)
    
    # Calculate overall attendance percentage
    overall_attendance = get_attendance_percentage(student)
    
    # Get subject-wise attendance
    subject_attendance = []
    warning_subjects = []
    for subject in subjects:
        attendance_data = get_subject_attendance(student, subject)
        percentage = attendance_data['attendance_percentage']
        
        subject_info = {
            'name': subject.subject_name,
            'percentage': percentage
        }
        subject_attendance.append(subject_info)
        
        # Check if attendance is below threshold
        if percentage < 75:
            warning_subjects.append({
                'name': subject.subject_name,
                'attendance_percentage': percentage
            })
    
    # Get today's classes
    today_classes = get_today_classes(student)
    today_total_classes = len(today_classes)
    today_classes_attended = sum(1 for cls in today_classes if cls['is_past'] and cls['attended'])
    
    # Get monthly attendance data for chart
    monthly_data = get_monthly_attendance_data(student)
    
    # Get recent notifications
    notifications = get_student_notifications(student, limit=5)
    notifications_list = []
    for notification in notifications:
        time_diff = timezone.now() - notification.created_at
        if time_diff.days > 0:
            time_ago = f"{time_diff.days} days ago"
        elif time_diff.seconds // 3600 > 0:
            time_ago = f"{time_diff.seconds // 3600} hours ago"
        else:
            time_ago = f"{time_diff.seconds // 60} minutes ago"
            
        icon = 'fa-bell'
        if notification.category == 'attendance':
            icon = 'fa-calendar-check'
        elif notification.category == 'leave':
            icon = 'fa-file-alt'
        elif notification.category == 'academics':
            icon = 'fa-book'
            
        notification_data = {
            'id': notification.notification_id,
            'title': notification.title,
            'message': notification.message,
            'category': notification.category,
            'is_unread': not notification.is_read,
            'time_ago': time_ago,
            'icon': icon
        }
        notifications_list.append(notification_data)
    
    # Subject attendance data for chart
    subject_attendance_data = []
    colors = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b']
    for i, subject in enumerate(subjects[:5]):  # Limit to 5 subjects for chart
        monthly_subject_data = get_monthly_attendance_data(student, subject=subject)
        subject_data = {
            'name': subject.subject_name,
            'attendance_data': monthly_subject_data['data'],
            'color': colors[i % len(colors)]
        }
        subject_attendance_data.append(subject_data)
    
    # AJAX request (for refreshing dashboard data)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('refresh') == 'true':
        data = {
            'overall_attendance': overall_attendance,
            'subject_attendance': subject_attendance,
            'today_classes': today_classes,
            'today_total_classes': today_total_classes,
            'today_classes_attended': today_classes_attended,
            'warning_subjects': warning_subjects,
            'notifications': notifications_list,
            'monthly_data': monthly_data,
            'subject_data': subject_attendance_data
        }
        return JsonResponse(data)
    
    # Render the dashboard template
    context = {
        'active_page': 'dashboard',
        'student': student,
        'overall_attendance': overall_attendance,
        'total_subjects': subjects.count(),
        'warning_subjects_count': len(warning_subjects),
        'warning_subjects': warning_subjects,
        'today_total_classes': today_total_classes,
        'today_classes_attended': today_classes_attended,
        'today_classes': today_classes,
        'subject_attendance': subject_attendance,
        'recent_attendance': get_recent_attendance(student),
        'notifications': notifications_list,
        'months': json.dumps(monthly_data['months']),
        'subject_attendance_data': subject_attendance_data,
        'current_academic_year': str(academic_year)
    }
    
    return render(request, 'student_portal/index.html', context)

# Attendance views
@login_required
def attendance(request):
    """Attendance summary view"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get subjects for current semester
    subjects = get_student_subjects(student, academic_year)
    
    # Get filter parameters
    selected_subject = request.GET.get('subject')
    selected_month = request.GET.get('month')
    selected_status = request.GET.get('status')
    export_format = request.GET.get('export')
    
    # Calculate overall attendance
    overall_attendance = get_attendance_percentage(student)
    
    # Get subject-wise attendance
    subject_attendance = []
    
    for subject in subjects:
        attendance_data = get_subject_attendance(student, subject)
        
        subject_info = {
            'id': subject.subject_id,
            'subject_code': subject.subject_code,
            'subject_name': subject.subject_name,
            'total_classes': attendance_data['total_classes'],
            'present_count': attendance_data['present_count'],
            'absent_count': attendance_data['absent_count'],
            'leave_count': attendance_data['leave_count'],
            'attendance_percentage': attendance_data['attendance_percentage']
        }
        subject_attendance.append(subject_info)
    
    # Calculate totals
    total_classes = sum(item['total_classes'] for item in subject_attendance)
    classes_attended = sum(item['present_count'] for item in subject_attendance)
    classes_missed = sum(item['absent_count'] for item in subject_attendance)
    leaves_approved = sum(item['leave_count'] for item in subject_attendance)
    
    # Get monthly attendance data for chart
    monthly_data = get_monthly_attendance_data(student)
    
    # Get recent attendance
    recent_attendance = get_recent_attendance(student, limit=10)
    
    # Month dropdown options
    current_month = timezone.now().month
    months = []
    for i in range(1, 13):
        month_name = calendar.month_name[i]
        months.append({'value': i, 'name': month_name})
    
    # Export attendance report if requested
    if export_format:
        if export_format.lower() == 'pdf':
            # Generate PDF report in a real application
            pass
        elif export_format.lower() == 'excel':
            # Generate Excel report in a real application
            pass
        
        # For now, return a simple message
        return JsonResponse({'success': True, 'message': f"Attendance exported as {export_format}"})
    
    context = {
        'active_page': 'attendance',
        'student': student,
        'current_academic_year': str(academic_year),
        'overall_percentage': overall_attendance,
        'total_classes': total_classes,
        'classes_attended': classes_attended,
        'classes_missed': classes_missed,
        'leaves_approved': leaves_approved,
        'subject_attendance': subject_attendance,
        'recent_attendance': recent_attendance,
        'all_subjects': subjects,
        'months': months,
        'selected_subject': selected_subject,
        'selected_month': selected_month,
        'selected_status': selected_status
    }
    
    return render(request, 'student_portal/attendance.html', context)

@login_required
def subject_attendance(request, subject_id):
    """Detailed attendance for a specific subject"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get subject
    try:
        subject = Subject.objects.get(subject_id=subject_id)
    except Subject.DoesNotExist:
        return render(request, 'error.html', {
            'error_title': 'Subject Not Found',
            'error_message': 'The requested subject could not be found.'
        })
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get subject attendance details
    attendance_data = get_subject_attendance(student, subject)
    
    # Calculate attendance percentage
    attendance_percentage = attendance_data['attendance_percentage']
    threshold_difference = max(0, 75 - attendance_percentage)
    
    # Calculate the number of classes needed to reach threshold
    classes_needed = 0
    if attendance_percentage < 75:
        total_present = attendance_data['present_count']
        total_classes = attendance_data['total_classes']
        
        # Calculate how many consecutive classes to attend to reach 75%
        i = 1
        while (total_present + i) / (total_classes + i) * 100 < 75:
            i += 1
        classes_needed = i
    
    # Get all attendance records for this subject
    faculty_subjects = FacultySubject.objects.filter(
        subject=subject,
        academic_year=academic_year
    )
    
    attendance_records = []
    raw_records = Attendance.objects.filter(
        student=student,
        faculty_subject__in=faculty_subjects
    ).select_related(
        'faculty_subject__faculty__user'
    ).order_by('-attendance_date')
    
    for record in raw_records:
        attendance_records.append({
            'date': record.attendance_date.strftime('%d %b, %Y'),
            'day': record.attendance_date.strftime('%A'),
            'start_time': '10:00 AM',  # Would come from timetable
            'end_time': '11:00 AM',    # Would come from timetable
            'topic': 'Regular Class',  # Would come from lesson plan
            'faculty_name': record.faculty_subject.faculty.user.full_name,
            'status': record.status,
            'remarks': ''
        })
    
    # Get monthly attendance data
    monthly_attendance = get_monthly_attendance_data(student, subject=subject)
    
    # Export if requested
    export_format = request.GET.get('export')
    if export_format:
        # In a real application, generate and serve the file
        return JsonResponse({'success': True})
    
    context = {
        'active_page': 'attendance',
        'student': student,
        'subject': {
            'id': subject.subject_id,
            'subject_name': subject.subject_name,
            'subject_code': subject.subject_code,
            'faculty_name': 'Multiple Faculties',  # Would get from faculty_subject
            'is_lab': False  # Would get from faculty_subject
        },
        'attendance_percentage': attendance_percentage,
        'threshold_difference': threshold_difference,
        'total_classes': attendance_data['total_classes'],
        'classes_attended': attendance_data['present_count'],
        'classes_missed': attendance_data['absent_count'],
        'leaves_approved': attendance_data['leave_count'],
        'classes_needed': classes_needed,
        'attendance_records': attendance_records,
        'monthly_attendance': json.dumps(monthly_attendance['data']),
        'months': json.dumps(monthly_attendance['months'])
    }
    
    return render(request, 'student_portal/subject_attendance.html', context)

@login_required
def attendance_history(request):
    """Attendance history view with semester-wise breakdown"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get current academic year
    current_academic_year = get_current_academic_year()
    
    # Get all semesters the student has been in
    current_semester = student.current_semester
    semesters = []
    
    # For each semester, get the subjects and attendance
    for semester in range(1, current_semester + 1):
        # Would come from semester_progression table in a real app
        is_current = semester == current_semester
        academic_year_str = str(current_academic_year) if is_current else f"{current_academic_year.year_start-1}-{current_academic_year.year_start}"
        
        # Get subjects for this semester
        semester_subjects = Subject.objects.filter(
            department=student.department,
            semester=semester
        )
        
        # Calculate overall attendance for this semester
        semester_attendance = 0
        subject_data = []
        
        for subject in semester_subjects:
            # In a real app, would get historical attendance records
            attendance_percentage = get_attendance_percentage(student, subject)
            
            subject_data.append({
                'id': subject.subject_id,
                'code': subject.subject_code,
                'name': subject.subject_name,
                'faculty': 'Prof. Smith',  # Would come from faculty_subject
                'total_classes': 40,  # Placeholder
                'attended_classes': int(40 * attendance_percentage / 100),  # Placeholder
                'attendance_percentage': attendance_percentage
            })
            
            semester_attendance += attendance_percentage
        
        # Calculate average percentage
        if semester_subjects.count() > 0:
            semester_attendance /= semester_subjects.count()
        
        semester_info = {
            'number': semester,
            'is_current': is_current,
            'academic_year': academic_year_str,
            'attendance_percentage': round(semester_attendance, 2),
            'subjects': subject_data
        }
        semesters.append(semester_info)
    
    # Generate observations based on attendance patterns
    observations = [
        {
            'title': 'Most Attended Subject',
            'description': 'You have the highest attendance in Computer Networks with 95%',
            'icon': 'fas fa-trophy text-success'
        },
        {
            'title': 'Improvement Needed',
            'description': 'Your attendance in Operating Systems needs attention (68%)',
            'icon': 'fas fa-exclamation-triangle text-warning'
        },
        {
            'title': 'Overall Trend',
            'description': 'Your attendance has improved by 8% compared to last semester',
            'icon': 'fas fa-chart-line text-info'
        },
        {
            'title': 'Consistency',
            'description': 'You\'ve maintained excellent attendance in lab sessions',
            'icon': 'fas fa-thumbs-up text-primary'
        }
    ]
    
    context = {
        'active_page': 'history',
        'student': student,
        'semesters': semesters,
        'observations': observations
    }
    
    return render(request, 'student_portal/attendance_history.html', context)

@login_required
@require_POST
def export_attendance_history(request):
    """Export complete attendance history"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get export format
    export_format = request.POST.get('format', 'PDF')
    
    # In a real application, would generate and serve the file
    
    return JsonResponse({
        'success': True,
        'message': f'Attendance history has been exported as {export_format}'
    })

@login_required
def get_day_attendance(request):
    """AJAX endpoint to get attendance for a specific day"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get student
    student = get_student_for_user(user)
    if not student:
        return JsonResponse({'success': False, 'message': 'Student record not found'})
    
    # Get date and subject parameters
    date_str = request.GET.get('date')
    subject_id = request.GET.get('subject')
    
    try:
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid date format'})
    
    # Query attendance record for this date
    query = Q(student=student, attendance_date=date)
    if subject_id:
        query &= Q(faculty_subject__subject_id=subject_id)
    
    try:
        attendance = Attendance.objects.filter(query).first()
        
        # If no attendance record found
        if not attendance:
            html_content = """
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i> No attendance record found for this date.
            </div>
            """
            return JsonResponse({
                'success': True,
                'html': html_content,
                'can_request_correction': False
            })
        
        # Generate HTML for attendance details
        status_class = {
            'present': 'present',
            'absent': 'absent', 
            'leave': 'leave'
        }.get(attendance.status, '')
        
        status_icon = {
            'present': 'fa-check-circle',
            'absent': 'fa-times-circle',
            'leave': 'fa-calendar-check'
        }.get(attendance.status, 'fa-question-circle')
        
        subject = attendance.faculty_subject.subject
        faculty = attendance.faculty_subject.faculty
        
        # Check if correction can be requested (e.g., within 3 days of attendance)
        can_request_correction = (timezone.now().date() - attendance.attendance_date).days <= 3
        
        html_content = f"""
        <div class="day-detail-status {status_class}">
            <i class="fas {status_icon} me-2"></i> {attendance.status.title()}
        </div>
        <div class="day-detail-info">
            <h6>Class Details</h6>
            <table class="table table-sm">
                <tr><th>Subject</th><td>{subject.subject_name}</td></tr>
                <tr><th>Topic</th><td>Regular Class</td></tr>
                <tr><th>Type</th><td>{'Practical' if attendance.faculty_subject.is_lab else 'Theory'}</td></tr>
                <tr><th>Time</th><td>10:00 AM - 11:00 AM</td></tr>
                <tr><th>Faculty</th><td>{faculty.user.full_name}</td></tr>
                <tr><th>Room</th><td>Room 101</td></tr>
            </table>
        </div>
        <div class="attendance-evidence">
            <h6>Attendance Evidence</h6>
            <p class="mb-2">Attendance recorded by: <span>{faculty.user.full_name}</span></p>
            <p class="mb-0">Recorded time: <span>{attendance.recorded_at.strftime('%d %b, %Y | %I:%M %p')}</span></p>
        </div>
        """
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'attendance_id': attendance.attendance_id,
            'status': attendance.status,
            'subject_name': subject.subject_name,
            'can_request_correction': can_request_correction
        })
        
    except Exception as e:
        logger.error(f"Error retrieving day attendance: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@require_POST
def request_attendance_correction(request):
    """Handle attendance correction requests"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get student
    student = get_student_for_user(user)
    if not student:
        return JsonResponse({'success': False, 'message': 'Student record not found'})
    
    try:
        # Get form data
        attendance_id = request.POST.get('attendance_id')
        current_status = request.POST.get('current_status')
        requested_status = request.POST.get('requested_status')
        reason = request.POST.get('reason')
        
        # Validate input
        if not attendance_id or not current_status or not requested_status or not reason:
            return JsonResponse({
                'success': False,
                'message': 'All fields are required'
            })
        
        # Get attendance record
        try:
            attendance = Attendance.objects.get(attendance_id=attendance_id, student=student)
        except Attendance.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Attendance record not found'
            })
        
        # Check if correction can be requested (e.g., within 3 days)
        if (timezone.now().date() - attendance.attendance_date).days > 3:
            return JsonResponse({
                'success': False,
                'message': 'Correction can only be requested within 3 days of attendance'
            })
        
        # Process upload if evidence is provided
        evidence_path = None
        if 'evidence' in request.FILES:
            evidence_file = request.FILES['evidence']
            
            # Validate file size (max 2MB)
            if evidence_file.size > 2 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'message': 'File size exceeds the 2MB limit'
                })
            
            # Validate file type
            allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
            if evidence_file.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'message': 'Only PDF, JPEG, and PNG files are allowed'
                })
            
            # Save file
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = f"correction_evidence_{student.student_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            evidence_path = fs.save(f"attendance_corrections/{filename}", evidence_file)
        
        # Create correction request
        correction = AttendanceCorrectionRequest.objects.create(
            student=student,
            attendance=attendance,
            current_status=current_status,
            requested_status=requested_status,
            reason=reason,
            evidence_path=evidence_path
        )
        
        # Create a notification for faculty
        faculty = attendance.faculty_subject.faculty
        Notification.objects.create(
            user=faculty.user,
            title="Attendance Correction Request",
            message=f"Student {student.user.full_name} has requested a correction for attendance on {attendance.attendance_date}",
            category="attendance"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Correction request submitted successfully',
            'request_id': correction.request_id
        })
        
    except Exception as e:
        logger.error(f"Error submitting correction request: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})

# Timetable views
@login_required
def timetable(request):
    """Timetable view"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get current date information
    current_date = timezone.now().date()
    day_of_week = current_date.strftime('%A')
    current_week_id = int(current_date.strftime('%W'))  # Week number in the year
    
    # Get JSON request for week navigation
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('format') == 'json':
        week_id = int(request.GET.get('week_id', current_week_id))
        week_start = datetime.datetime.strptime(f"{current_date.year}-{week_id}-1", "%Y-%W-%w").date()
        week_end = week_start + datetime.timedelta(days=6)
        
        return JsonResponse({
            'success': True,
            'week_id': week_id,
            'week_label': f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        })
    
    # Generate weekly timetable
    weekly_timetable = generate_weekly_timetable(student, academic_year)
    
    # Get daily classes
    daily_classes = get_daily_classes(student, current_date)
    
    # Get all classes in a list view
    list_view_classes = get_list_view_classes(student, academic_year)
    
    # Get today's classes with attendance status
    today_classes = get_today_classes(student)
    
    # Get faculty contacts for student's classes
    faculty_contacts = get_faculty_contacts(student, academic_year)
    
    # Get upcoming schedule changes
    schedule_changes = get_schedule_changes(student)
    
    context = {
        'active_page': 'timetable',
        'student': student,
        'current_date': current_date,
        'current_week_id': current_week_id,
        'weekly_timetable': weekly_timetable,
        'daily_classes': daily_classes,
        'list_view_classes': list_view_classes,
        'today_classes': today_classes,
        'faculty_contacts': faculty_contacts,
        'schedule_changes': schedule_changes
    }
    
    return render(request, 'student_portal/timetable.html', context)

@login_required
def day_timetable(request, day):
    """View timetable for a specific day"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Parse day parameter
    try:
        if '-' in day:  # Assume YYYY-MM-DD format
            selected_date = datetime.datetime.strptime(day, '%Y-%m-%d').date()
            selected_day_of_week = selected_date.strftime('%A')
        else:  # Assume day name like 'Monday'
            selected_day_of_week = day.capitalize()
            # Find the next occurrence of this day
            current_date = timezone.now().date()
            days_ahead = (list(calendar.day_name).index(selected_day_of_week) - current_date.weekday()) % 7
            selected_date = current_date + datetime.timedelta(days=days_ahead)
    except (ValueError, TypeError):
        return render(request, 'error.html', {
            'error_title': 'Invalid Date',
            'error_message': 'The provided date or day is invalid.'
        })
    
    # Get classes for the selected day
    daily_classes = get_daily_classes(student, selected_date)
    
    # Redirect to timetable view with the daily tab active
    return redirect('student_portal:timetable')

# Helper functions for timetable
def generate_weekly_timetable(student, academic_year):
    """Generate weekly timetable structure"""
    # Get class section and batch
    class_section = student.class_section
    batch = student.batch
    
    # Get all timetable entries for this class section
    timetable_entries = Timetable.objects.filter(
        academic_year=academic_year,
        faculty_subject__class_section=class_section
    ).select_related(
        'faculty_subject__subject',
        'faculty_subject__faculty__user'
    ).order_by('day_of_week', 'start_time')
    
    # For lab classes, filter by student's batch
    if batch:
        # Get theory classes (no batch)
        theory_entries = timetable_entries.filter(
            faculty_subject__is_lab=False
        )
        
        # Get lab classes for student's batch
        lab_entries = timetable_entries.filter(
            faculty_subject__is_lab=True,
            faculty_subject__batch=batch
        )
        
        # Combine theory and lab entries
        timetable_entries = theory_entries | lab_entries
    
    # Create a structure for the week
    # Find all unique time slots
    all_times = set()
    for entry in timetable_entries:
        all_times.add((entry.start_time, entry.end_time))
    
    time_slots = sorted(list(all_times))
    
    # Create weekly structure
    weekly_structure = {
        'time_slots': [],
        'breaks': [
            {'start_time': '1:00 PM', 'end_time': '2:00 PM', 'name': 'Lunch Break'}
        ]
    }
    
    # Days of the week
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Fill in the structure
    for start_time, end_time in time_slots:
        time_slot = {
            'start_time': start_time.strftime('%I:%M %p'),
            'end_time': end_time.strftime('%I:%M %p'),
            'days': []
        }
        
        # Add entry for each day
        for day in days:
            day_entry = {'class': None}
            
            # Find class for this day and time slot
            day_class = timetable_entries.filter(
                day_of_week=day,
                start_time=start_time,
                end_time=end_time
            ).first()
            
            if day_class:
                faculty_subject = day_class.faculty_subject
                subject = faculty_subject.subject
                faculty = faculty_subject.faculty
                
                day_entry['class'] = {
                    'subject_name': subject.subject_name,
                    'faculty_name': faculty.user.full_name,
                    'room_number': day_class.room_number,
                    'is_lab': faculty_subject.is_lab
                }
            
            time_slot['days'].append(day_entry)
        
        weekly_structure['time_slots'].append(time_slot)
    
    return weekly_structure

def get_daily_classes(student, date):
    """Get classes for a specific day"""
    day_of_week = date.strftime('%A')
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get timetable entries for this day
    timetable_entries = Timetable.objects.filter(
        day_of_week=day_of_week,
        academic_year=academic_year,
        faculty_subject__class_section=student.class_section
    ).select_related(
        'faculty_subject__subject',
        'faculty_subject__faculty__user'
    ).order_by('start_time')
    
    # For lab classes, filter by student's batch
    if student.batch:
        # Get theory classes (no batch)
        theory_entries = timetable_entries.filter(
            faculty_subject__is_lab=False
        )
        
        # Get lab classes for student's batch
        lab_entries = timetable_entries.filter(
            faculty_subject__is_lab=True,
            faculty_subject__batch=student.batch
        )
        
        # Combine theory and lab entries
        timetable_entries = theory_entries | lab_entries
    
    # Convert to list of dictionaries with formatted info
    classes = []
    for entry in timetable_entries:
        faculty_subject = entry.faculty_subject
        subject = faculty_subject.subject
        faculty = faculty_subject.faculty
        
        class_info = {
            'subject_name': subject.subject_name,
            'subject_code': subject.subject_code,
            'faculty_name': faculty.user.full_name,
            'room_number': entry.room_number,
            'start_time': entry.start_time.strftime('%I:%M %p'),
            'end_time': entry.end_time.strftime('%I:%M %p'),
            'is_lab': faculty_subject.is_lab,
            'topic': 'Regular Class'  # In real app, would come from lesson plan
        }
        classes.append(class_info)
    
    return classes

def get_list_view_classes(student, academic_year):
    """Get all classes in a list view format"""
    # Get timetable entries for this class section
    timetable_entries = Timetable.objects.filter(
        academic_year=academic_year,
        faculty_subject__class_section=student.class_section
    ).select_related(
        'faculty_subject__subject',
        'faculty_subject__faculty__user'
    ).order_by('day_of_week', 'start_time')
    
    # For lab classes, filter by student's batch
    if student.batch:
        # Get theory classes (no batch)
        theory_entries = timetable_entries.filter(
            faculty_subject__is_lab=False
        )
        
        # Get lab classes for student's batch
        lab_entries = timetable_entries.filter(
            faculty_subject__is_lab=True,
            faculty_subject__batch=student.batch
        )
        
        # Combine theory and lab entries
        timetable_entries = theory_entries | lab_entries
    
    # Convert to list of dictionaries with formatted info
    classes = []
    for entry in timetable_entries:
        faculty_subject = entry.faculty_subject
        subject = faculty_subject.subject
        faculty = faculty_subject.faculty
        
        class_info = {
            'day_of_week': entry.day_of_week,
            'subject_name': subject.subject_name,
            'subject_code': subject.subject_code,
            'faculty_name': faculty.user.full_name,
            'room_number': entry.room_number,
            'start_time': entry.start_time.strftime('%I:%M %p'),
            'end_time': entry.end_time.strftime('%I:%M %p'),
            'is_lab': faculty_subject.is_lab
        }
        classes.append(class_info)
    
    return classes

def get_faculty_contacts(student, academic_year):
    """Get contact information for faculties teaching the student"""
    # Get unique faculties from FacultySubject
    faculty_subject_entries = FacultySubject.objects.filter(
        academic_year=academic_year,
        class_section=student.class_section
    ).select_related(
        'faculty__user',
        'subject'
    )
    
    # For lab classes, filter by student's batch
    if student.batch:
        # Get theory classes (no batch)
        theory_entries = faculty_subject_entries.filter(
            is_lab=False
        )
        
        # Get lab classes for student's batch
        lab_entries = faculty_subject_entries.filter(
            is_lab=True,
            batch=student.batch
        )
        
        # Combine theory and lab entries
        faculty_subject_entries = theory_entries | lab_entries
    
    # Group by faculty and collect subjects
    faculty_map = {}
    for entry in faculty_subject_entries:
        faculty = entry.faculty
        subject = entry.subject
        
        if faculty.faculty_id not in faculty_map:
            faculty_map[faculty.faculty_id] = {
                'id': faculty.faculty_id,
                'name': faculty.user.full_name,
                'email': faculty.user.email,
                'phone': '+91 98765 43210',  # Placeholder
                'profile_photo': None,  # Would come from a photo field
                'subjects': []
            }
        
        faculty_map[faculty.faculty_id]['subjects'].append(subject.subject_name)
    
    # Convert dict to list
    faculty_contacts = list(faculty_map.values())
    
    # Make subjects unique
    for faculty in faculty_contacts:
        faculty['subjects'] = list(set(faculty['subjects']))
    
    return faculty_contacts

def get_schedule_changes(student):
    """Get upcoming schedule changes"""
    # In a real app, would come from a schedule_changes table
    # For now, return dummy data
    changes = [
        {
            'date': datetime.date.today() + datetime.timedelta(days=5),
            'title': 'Database Systems Lab Rescheduled',
            'description': 'The lab session has been moved to Room 202 due to maintenance work in Lab 1.',
            'type': 'rescheduled'
        },
        {
            'date': datetime.date.today() + datetime.timedelta(days=2),
            'title': 'Programming Lab Cancelled',
            'description': 'Due to faculty meeting, the Programming Lab scheduled for Friday is cancelled.',
            'type': 'cancelled'
        },
        {
            'date': datetime.date.today() + datetime.timedelta(days=7),
            'title': 'Substitution: Web Development',
            'description': 'Prof. Gupta will be substituting for Prof. Kumar for Web Development class.',
            'type': 'substitution'
        },
        {
            'date': datetime.date.today() + datetime.timedelta(days=3),
            'title': 'Extra Class: Operating Systems',
            'description': 'Additional class scheduled for syllabus completion from 3:00 PM to 4:00 PM.',
            'type': 'added'
        }
    ]
    
    for change in changes:
        change['date'] = change['date'].strftime('%b %d')
    
    return changes

# Leave application views
@login_required
def leave_application(request):
    """Leave application view"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Get tomorrow's date for form min date
    tomorrow = timezone.now().date() + datetime.timedelta(days=1)
    
    # Get leave applications
    pending_applications = get_leave_applications(student, status=['pending', 'faculty_approved'])
    previous_applications = get_leave_applications(student, status=['approved', 'rejected', 'cancelled'])
    
    # Calculate leave statistics
    leave_limit = 15  # Default limit per academic year, can be configured in settings
    approved_leaves = calculate_leaves_taken(student, academic_year)
    pending_leaves = sum(
        (app.end_date - app.start_date).days + 1 
        for app in pending_applications
    )
    rejected_leaves = sum(
        (app.end_date - app.start_date).days + 1 
        for app in previous_applications.filter(status='rejected')
    )
    leave_balance = max(0, leave_limit - approved_leaves - pending_leaves)
    
    # Get leave types
    leave_types = [
        {'value': 'medical', 'name': 'Medical Leave'},
        {'value': 'family', 'name': 'Family Emergency'},
        {'value': 'event', 'name': 'Event Participation'},
        {'value': 'personal', 'name': 'Personal Work'},
        {'value': 'other', 'name': 'Other'}
    ]
    
    # Format leave applications for display
    pending_apps_formatted = []
    for app in pending_applications:
        duration = (app.end_date - app.start_date).days + 1
        
        app_info = {
            'id': app.leave_id,
            'application_id': f'LA{app.leave_id:06d}',
            'start_date': app.start_date.strftime('%d %b, %Y'),
            'end_date': app.end_date.strftime('%d %b, %Y'),
            'duration': duration,
            'reason_type': app.reason[:20] + '...' if len(app.reason) > 20 else app.reason,
            'created_at': app.created_at.strftime('%d %b, %Y'),
            'status': app.status
        }
        pending_apps_formatted.append(app_info)
    
    previous_apps_formatted = []
    for app in previous_applications:
        duration = (app.end_date - app.start_date).days + 1
        
        app_info = {
            'id': app.leave_id,
            'application_id': f'LA{app.leave_id:06d}',
            'start_date': app.start_date.strftime('%d %b, %Y'),
            'end_date': app.end_date.strftime('%d %b, %Y'),
            'duration': duration,
            'reason_type': app.reason[:20] + '...' if len(app.reason) > 20 else app.reason,
            'created_at': app.created_at.strftime('%d %b, %Y'),
            'status': app.status
        }
        previous_apps_formatted.append(app_info)
    
    context = {
        'active_page': 'leave',
        'student': student,
        'leave_balance': leave_balance,
        'leave_limit': leave_limit,
        'approved_leaves': approved_leaves,
        'pending_leaves': pending_leaves,
        'rejected_leaves': rejected_leaves,
        'pending_applications': pending_apps_formatted,
        'previous_applications': previous_apps_formatted,
        'leave_types': leave_types,
        'tomorrow': tomorrow,
        'current_academic_year': str(academic_year)
    }
    
    return render(request, 'student_portal/leave_application.html', context)

@login_required
def create_leave_application(request):
    """Create a new leave application"""
    if request.method != 'POST':
        return redirect('student_portal:leave_application')
    
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('student_portal:leave_application')
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        messages.error(request, 'Your student profile could not be found.')
        return redirect('student_portal:leave_application')
    
    try:
        # Get form data
        leave_type = request.POST.get('leave_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason')
        acknowledgment = request.POST.get('acknowledgment') == 'on'
        
        # Validate required fields
        if not leave_type or not start_date_str or not end_date_str or not reason or not acknowledgment:
            messages.error(request, 'All required fields must be filled out.')
            return redirect('student_portal:leave_application')
        
        # Parse dates
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return redirect('student_portal:leave_application')
        
        # Validate dates
        if start_date < timezone.now().date():
            messages.error(request, 'Start date cannot be in the past.')
            return redirect('student_portal:leave_application')
        
        if end_date < start_date:
            messages.error(request, 'End date cannot be before start date.')
            return redirect('student_portal:leave_application')
        
        # Calculate duration
        duration = (end_date - start_date).days + 1
        
        # Check leave balance
        academic_year = get_current_academic_year()
        leave_limit = 15  # Default limit
        approved_leaves = calculate_leaves_taken(student, academic_year)
        pending_leaves = sum(
            (app.end_date - app.start_date).days + 1 
            for app in get_leave_applications(student, status=['pending', 'faculty_approved'])
        )
        leave_balance = max(0, leave_limit - approved_leaves - pending_leaves)
        
        if duration > leave_balance:
            messages.error(request, f'You do not have enough leave balance. Available: {leave_balance} days.')
            return redirect('student_portal:leave_application')
        
        # Process document if provided
        document_path = None
        if 'document' in request.FILES:
            document = request.FILES['document']
            
            # Validate file size (max 2MB)
            if document.size > 2 * 1024 * 1024:
                messages.error(request, 'File size exceeds the 2MB limit.')
                return redirect('student_portal:leave_application')
            
            # Validate file type
            allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
            if document.content_type not in allowed_types:
                messages.error(request, 'Only PDF, JPEG, and PNG files are allowed.')
                return redirect('student_portal:leave_application')
            
            # Save document
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = f"leave_document_{student.student_id}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            document_path = fs.save(f"leave_documents/{filename}", document)
        
        # Create leave application
        leave_application = LeaveApplication.objects.create(
            student=student,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            document_path=document_path,
            status='pending'
        )
        
        # Create notifications for faculty
        faculty_ids = set()
        
        # Get missed classes from selected dates
        missed_classes = request.POST.getlist('missed_classes')
        if missed_classes:
            for class_id in missed_classes:
                # In a real app, would parse class ID and notify relevant faculty
                pass
        
        # Get all faculty teaching this student
        faculty_subjects = FacultySubject.objects.filter(
            academic_year=academic_year,
            class_section=student.class_section
        ).values_list('faculty_id', flat=True).distinct()
        
        faculty_ids.update(faculty_subjects)
        
        # Notify faculty
        for faculty_id in faculty_ids:
            try:
                faculty = Faculty.objects.get(faculty_id=faculty_id)
                Notification.objects.create(
                    user=faculty.user,
                    title="Leave Application Received",
                    message=f"Student {student.user.full_name} has applied for leave from {start_date} to {end_date}.",
                    category="leave"
                )
            except Faculty.DoesNotExist:
                continue
        
        messages.success(request, 'Leave application submitted successfully!')
        return redirect('student_portal:leave_application')
        
    except Exception as e:
        logger.error(f"Error creating leave application: {e}", exc_info=True)
        messages.error(request, f'An error occurred while submitting your application: {str(e)}')
        return redirect('student_portal:leave_application')

@login_required
def leave_application_detail(request, leave_id):
    """View details of a specific leave application"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get leave application
    try:
        leave = LeaveApplication.objects.get(leave_id=leave_id, student=student)
    except LeaveApplication.DoesNotExist:
        return render(request, 'error.html', {
            'error_title': 'Application Not Found',
            'error_message': 'The requested leave application could not be found.'
        })
    
    # Format leave details
    leave_detail = {
        'id': leave.leave_id,
        'application_id': f'LA{leave.leave_id:06d}',
        'start_date': leave.start_date.strftime('%d %b, %Y'),
        'end_date': leave.end_date.strftime('%d %b, %Y'),
        'duration': (leave.end_date - leave.start_date).days + 1,
        'reason': leave.reason,
        'document': leave.document_path,
        'status': leave.status,
        'created_at': leave.created_at.strftime('%d %b, %Y at %I:%M %p')
    }
    
    # Format approvals
    approvals = []
    
    # Faculty approval
    if leave.faculty_approval:
        try:
            faculty = Faculty.objects.get(faculty_id=leave.faculty_approval)
            faculty_name = faculty.user.full_name
        except Faculty.DoesNotExist:
            faculty_name = "Unknown Faculty"
            
        approvals.append({
            'role': 'Faculty',
            'name': faculty_name,
            'status': 'approved' if leave.status in ['faculty_approved', 'approved'] else 'pending',
            'date': timezone.now().strftime('%d %b, %Y | %I:%M %p'),
            'comment': 'Approved based on request.'
        })
    else:
        approvals.append({
            'role': 'Faculty',
            'name': 'Pending Approval',
            'status': 'pending',
            'date': '',
            'comment': ''
        })
    
    # Lab assistant approval
    if leave.status == 'approved':
        approvals.append({
            'role': 'Lab Assistant',
            'name': 'Lab Staff',
            'status': 'approved',
            'date': timezone.now().strftime('%d %b, %Y | %I:%M %p'),
            'comment': 'Approved for requested dates.'
        })
    else:
        approvals.append({
            'role': 'Lab Assistant',
            'name': 'Pending Approval',
            'status': 'pending',
            'date': '',
            'comment': ''
        })
    
    context = {
        'active_page': 'leave',
        'student': student,
        'leave': leave_detail,
        'approvals': approvals
    }
    
    return render(request, 'student_portal:leave_application_detail', context)

@login_required
def cancel_leave_application(request, leave_id):
    """Cancel a pending leave application"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('student_portal:leave_application')
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        messages.error(request, 'Your student profile could not be found.')
        return redirect('student_portal:leave_application')
    
    # Get leave application
    try:
        leave = LeaveApplication.objects.get(leave_id=leave_id, student=student)
    except LeaveApplication.DoesNotExist:
        messages.error(request, 'The requested leave application could not be found.')
        return redirect('student_portal:leave_application')
    
    # Check if application can be cancelled
    if leave.status not in ['pending', 'faculty_approved']:
        messages.error(request, 'Only pending applications can be cancelled.')
        return redirect('student_portal:leave_application')
    
    # Cancel application
    leave.status = 'cancelled'
    leave.save()
    
    # Create notification for faculty if faculty has approved
    if leave.faculty_approval:
        try:
            faculty = Faculty.objects.get(faculty_id=leave.faculty_approval)
            Notification.objects.create(
                user=faculty.user,
                title="Leave Application Cancelled",
                message=f"Student {student.user.full_name} has cancelled their leave application from {leave.start_date} to {leave.end_date}.",
                category="leave"
            )
        except Faculty.DoesNotExist:
            pass
    
    messages.success(request, 'Leave application has been cancelled successfully.')
    return redirect('student_portal:leave_application')

# Notification views
@login_required
def notifications(request):
    """View notifications"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get filter parameters
    filter_type = request.GET.get('filter', 'all')
    search_query = request.GET.get('search', '')
    
    # Get notifications
    notifications_query = Notification.objects.filter(user=user).order_by('-created_at')
    
    # Apply filters
    if filter_type != 'all':
        notifications_query = notifications_query.filter(category=filter_type)
    
    if search_query:
        notifications_query = notifications_query.filter(
            Q(title__icontains=search_query) | 
            Q(message__icontains=search_query)
        )
    
    # Paginate results
    paginator = Paginator(notifications_query, 10)
    page_number = request.GET.get('page', 1)
    notifications = paginator.get_page(page_number)
    
    # Format notifications
    notifications_list = []
    for notification in notifications:
        time_diff = timezone.now() - notification.created_at
        if time_diff.days > 0:
            time_ago = f"{time_diff.days} days ago"
        elif time_diff.seconds // 3600 > 0:
            time_ago = f"{time_diff.seconds // 3600} hours ago"
        else:
            time_ago = f"{time_diff.seconds // 60} minutes ago"
            
        notification_data = {
            'id': notification.notification_id,
            'title': notification.title,
            'message': notification.message,
            'category': notification.category,
            'is_read': notification.is_read,
            'created_at': time_ago
        }
        notifications_list.append(notification_data)
    
    # Get notification settings
    try:
        notification_settings = NotificationSetting.objects.get(user=user)
    except NotificationSetting.DoesNotExist:
        notification_settings = NotificationSetting.objects.create(user=user)
    
    context = {
        'active_page': 'notifications',
        'student': student,
        'notifications': notifications_list,
        'is_paginated': notifications.has_other_pages(),
        'page_obj': notifications,
        'paginator': paginator,
        'notification_settings': notification_settings
    }
    
    return render(request, 'student_portal/notifications.html', context)

@login_required
def get_notification_details(request):
    """AJAX endpoint to get notification details"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get notification ID
    notification_id = request.GET.get('notification_id')
    if not notification_id:
        return JsonResponse({'success': False, 'message': 'Notification ID is required'})
    
    try:
        notification = Notification.objects.get(notification_id=notification_id, user=user)
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Notification not found'})
    
    # Generate HTML for notification detail
    category_icon = {
        'attendance': 'fa-calendar-check',
        'leave': 'fa-file-alt',
        'academics': 'fa-book',
        'system': 'fa-cog'
    }.get(notification.category, 'fa-bell')
    
    html_content = f"""
    <div class="notification-detail-header">
        <div class="notification-detail-icon {notification.category}">
            <i class="fas {category_icon}"></i>
        </div>
        <div class="notification-detail-title">
            <h5>{notification.title}</h5>
            <p class="notification-detail-time">{notification.created_at.strftime('%B %d, %Y, %I:%M %p')}</p>
        </div>
    </div>
    <div class="notification-detail-content">
        <p>{notification.message}</p>
    </div>
    """
    
    # Optional: Mark as read when viewed
    if not notification.is_read:
        notification.is_read = True
        notification.save()
    
    return JsonResponse({
        'success': True,
        'html': html_content,
        'is_read': notification.is_read
    })

@login_required
@require_POST
def mark_notification_read(request):
    """Mark a notification as read"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get notification ID
    notification_id = request.POST.get('notification_id')
    if not notification_id:
        return JsonResponse({'success': False, 'message': 'Notification ID is required'})
    
    try:
        notification = Notification.objects.get(notification_id=notification_id, user=user)
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Notification not found'})
    
    # Mark as read
    notification.is_read = True
    notification.save()
    
    return JsonResponse({'success': True})

@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Update all unread notifications
    Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    
    return JsonResponse({'success': True})

@login_required
@require_POST
def update_notification_settings(request):
    """Update notification settings"""
    user = request.user
    
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    try:
        settings, created = NotificationSetting.objects.get_or_create(user=user)
        
        # Update settings from form
        settings.attendance_emails = request.POST.get('attendance_emails') == 'on'
        settings.leave_emails = request.POST.get('leave_emails') == 'on'
        settings.timetable_emails = request.POST.get('timetable_emails') == 'on'
        settings.system_emails = request.POST.get('system_emails') == 'on'
        
        settings.attendance_inapp = request.POST.get('attendance_inapp') == 'on'
        settings.leave_inapp = request.POST.get('leave_inapp') == 'on'
        settings.timetable_inapp = request.POST.get('timetable_inapp') == 'on'
        settings.system_inapp = request.POST.get('system_inapp') == 'on'
        
        settings.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error updating notification settings: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})

# Profile views
@login_required
def profile(request):
    """Profile view"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get student profile (additional details)
    try:
        profile = StudentProfile.objects.get(student=student)
    except StudentProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = StudentProfile.objects.create(student=student)
    
    # Get user preferences
    try:
        preferences = UserPreference.objects.get(user=user)
    except UserPreference.DoesNotExist:
        preferences = UserPreference.objects.create(user=user)
    
    # Get current academic year
    academic_year = get_current_academic_year()
    
    # Available blood groups
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    
    # Combine student and profile data
    student_data = {
        'enrollment_number': student.user.enrollment_number,
        'roll_number': student.roll_number,
        'department': student.department,
        'class_section': student.class_section,
        'batch': student.batch,
        'current_semester': student.current_semester,
        'admission_year': student.admission_year,
        'dob': student.dob,
        'profile_photo': profile.profile_photo,
        'contact_number': profile.contact_number,
        'address': profile.address,
        'blood_group': profile.blood_group,
        'skills': profile.skills or [],
        'linkedin_profile': profile.linkedin_profile,
        'github_profile': profile.github_profile,
        'twitter_profile': profile.twitter_profile,
        'instagram_profile': profile.instagram_profile,
        'father_name': profile.father_name,
        'father_occupation': profile.father_occupation,
        'father_contact': profile.father_contact,
        'mother_name': profile.mother_name,
        'mother_occupation': profile.mother_occupation,
        'mother_contact': profile.mother_contact,
        'emergency_contact': profile.emergency_contact,
        'emergency_contact_relation': profile.emergency_contact_relation
    }
    
    context = {
        'active_page': 'profile',
        'user': user,
        'student': student_data,
        'preferences': preferences,
        'blood_groups': blood_groups,
        'current_academic_year': str(academic_year)
    }
    
    return render(request, 'student_portal/profile.html', context)

@login_required
@require_POST
def edit_profile(request):
    """Update student profile"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('student_portal:profile')
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        messages.error(request, 'Your student profile could not be found.')
        return redirect('student_portal:profile')
    
    # Get or create profile
    profile, created = StudentProfile.objects.get_or_create(student=student)
    
    # Update profile fields
    profile.contact_number = request.POST.get('contact_number', '')
    profile.address = request.POST.get('address', '')
    profile.blood_group = request.POST.get('blood_group', '')
    profile.emergency_contact = request.POST.get('emergency_contact', '')
    profile.emergency_contact_relation = request.POST.get('emergency_contact_relation', '')
    
    # Social media links
    profile.linkedin_profile = request.POST.get('linkedin_profile', '')
    profile.github_profile = request.POST.get('github_profile', '')
    profile.twitter_profile = request.POST.get('twitter_profile', '')
    profile.instagram_profile = request.POST.get('instagram_profile', '')
    
    profile.save()
    
    messages.success(request, 'Profile updated successfully!')
    return redirect('student_portal:profile')

@login_required
@require_POST
def update_skills(request):
    """Update student skills"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return JsonResponse({'success': False, 'message': 'Student record not found'})
    
    # Get or create profile
    profile, created = StudentProfile.objects.get_or_create(student=student)
    
    # Update skills
    skills_list = request.POST.get('skills', '').split(',')
    skills_list = [skill.strip() for skill in skills_list if skill.strip()]
    
    profile.skills = skills_list
    profile.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Skills updated successfully.',
        'skills': skills_list
    })

@login_required
@require_POST
def save_preferences(request):
    """Save user interface preferences"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    try:
        # Get or create preferences
        preferences, created = UserPreference.objects.get_or_create(user=user)
        
        # Get current theme to check if it changed
        current_theme = preferences.theme
        
        # Update preferences
        preferences.theme = request.POST.get('theme', 'light')
        preferences.default_view = request.POST.get('default_view', 'dashboard')
        preferences.enable_notifications = request.POST.get('enable_notifications') == 'on'
        
        preferences.save()
        
        return JsonResponse({
            'success': True,
            'theme_changed': current_theme != preferences.theme
        })
        
    except Exception as e:
        logger.error(f"Error saving preferences: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def upload_profile_photo(request):
    """Handle profile photo uploads"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('student_portal:profile')
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        messages.error(request, 'Your student profile could not be found.')
        return redirect('student_portal:profile')
    
    # Get or create profile
    profile, created = StudentProfile.objects.get_or_create(student=student)
    
    if request.method == 'POST' and 'profile_photo' in request.FILES:
        uploaded_file = request.FILES['profile_photo']
        
        # Validate file size (max 2MB)
        if uploaded_file.size > 2 * 1024 * 1024:
            messages.error(request, 'File size exceeds the 2MB limit.')
            return redirect('student_portal:profile')
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif']
        if uploaded_file.content_type not in allowed_types:
            messages.error(request, 'Only JPEG, PNG, and GIF images are allowed.')
            return redirect('student_portal:profile')
        
        # Create directory for profile photos
        profile_photos_dir = os.path.join(settings.MEDIA_ROOT, 'profile_photos')
        os.makedirs(profile_photos_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(uploaded_file.name)[1]
        filename = f"profile_{student.student_id}_{int(timezone.now().timestamp())}{file_extension}"
        
        # Save the file
        fs = FileSystemStorage(location=profile_photos_dir)
        saved_filename = fs.save(filename, uploaded_file)
        
        # Update profile photo path
        profile.profile_photo = f"profile_photos/{saved_filename}"
        profile.save()
        
        messages.success(request, 'Profile photo uploaded successfully!')
    else:
        messages.error(request, 'No file was uploaded.')
    
    return redirect('student_portal:profile')

@login_required
@require_POST
def change_password(request):
    """Change user password"""
    user = request.user
    
    # Validate input
    current_password = request.POST.get('current_password')
    new_password = request.POST.get('new_password')
    confirm_password = request.POST.get('confirm_password')
    
    if not current_password or not new_password or not confirm_password:
        messages.error(request, 'All fields are required.')
        return redirect('student_portal:profile')
    
    if new_password != confirm_password:
        messages.error(request, 'New password and confirmation do not match.')
        return redirect('student_portal:profile')
    
    # Check current password
    if not user.check_password(current_password):
        messages.error(request, 'Current password is incorrect.')
        return redirect('student_portal:profile')
    
    # Validate password strength
    if len(new_password) < 8:
        messages.error(request, 'Password must be at least 8 characters long.')
        return redirect('student_portal:profile')
    
    # Update password
    user.set_password(new_password)
    user.save()
    
    messages.success(request, 'Password changed successfully. Please log in with your new password.')
    return redirect('logout')

# Logging view
@login_required
def log_view(request):
    """View for logging actions from frontend"""
    if request.method == 'POST':
        message = request.POST.get('message', '')
        log_type = request.POST.get('type', 'info')
        
        # Log the message with appropriate level
        if log_type == 'error':
            logger.error(message)
        elif log_type == 'warning':
            logger.warning(message)
        else:
            logger.info(message)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

# Handler for Daily Attendance view
@login_required
def daily_attendance(request):
    """Daily attendance details view"""
    user = request.user
    
    # Validate student role
    if user.get_role() != 'student':
        return render(request, 'error.html', {
            'error_title': 'Access Denied',
            'error_message': 'You do not have permission to access this page.'
        })
    
    # Get student record
    student = get_student_for_user(user)
    if not student:
        return render(request, 'error.html', {
            'error_title': 'Profile Error',
            'error_message': 'Your student profile could not be found.'
        })
    
    # Get query parameters
    subject_id = request.GET.get('subject')
    month = request.GET.get('month')
    status = request.GET.get('status')
    
    # Get current date or selected date
    try:
        selected_date = request.GET.get('date')
        if selected_date:
            current_date = datetime.datetime.strptime(selected_date, '%Y-%m-%d').date()
        else:
            current_date = timezone.now().date()
    except (ValueError, TypeError):
        current_date = timezone.now().date()
    
    # Initialize date navigation
    current_month = {
        'name': current_date.strftime('%B %Y'),
        'year': current_date.year,
        'number': current_date.month
    }
    
    # Previous and next months
    if current_date.month == 1:
        prev_month = {
            'number': 12,
            'year': current_date.year - 1
        }
    else:
        prev_month = {
            'number': current_date.month - 1,
            'year': current_date.year
        }
    
    if current_date.month == 12:
        next_month = {
            'number': 1,
            'year': current_date.year + 1
        }
    else:
        next_month = {
            'number': current_date.month + 1,
            'year': current_date.year
        }
    
    # Get subject information if a subject is selected
    subject_info = None
    if subject_id:
        try:
            subject = Subject.objects.get(subject_id=subject_id)
            attendance_data = get_subject_attendance(student, subject)
            
            subject_info = {
                'name': subject.subject_name,
                'code': subject.subject_code,
                'faculty': 'Multiple Faculties',  # Would come from faculty_subject
                'icon': 'fas fa-book',
                'type': 'Theory & Lab' if subject.has_theory and subject.has_lab else ('Theory' if subject.has_theory else 'Lab'),
                'semester': subject.semester,
                'credits': subject.credits,
                'attendance_percentage': attendance_data['attendance_percentage'],
                'total_classes': attendance_data['total_classes'],
                'attended_classes': attendance_data['present_count'],
                'absent_classes': attendance_data['absent_count']
            }
        except Subject.DoesNotExist:
            pass
    
    # Generate calendar structure for the month
    calendar_weeks = generate_monthly_calendar(student, current_date.year, current_date.month, subject_id)
    
    # Get attendance records
    attendance_records = get_detailed_attendance_records(student, subject_id, month, status)
    
    # Get trend data
    trend_data = get_monthly_attendance_data(student, subject=subject_id if subject_id else None)
    
    # List of months for dropdown
    months = [
        {"number": 1, "name": "January"},
        {"number": 2, "name": "February"},
        {"number": 3, "name": "March"},
        {"number": 4, "name": "April"},
        {"number": 5, "name": "May"},
        {"number": 6, "name": "June"},
        {"number": 7, "name": "July"},
        {"number": 8, "name": "August"},
        {"number": 9, "name": "September"},
        {"number": 10, "name": "October"},
        {"number": 11, "name": "November"},
        {"number": 12, "name": "December"}
    ]
    
    # Get all subjects for filter
    subjects = get_student_subjects(student)
    
    context = {
        'active_page': 'attendance',
        'student': student,
        'current_date': current_date,
        'current_month': current_month,
        'prev_month': prev_month,
        'next_month': next_month,
        'calendar_weeks': calendar_weeks,
        'attendance_records': attendance_records,
        'trend_data': trend_data,
        'subject_info': subject_info,
        'subjects': subjects,
        'months': months,
        'selected_subject': subject_id,
        'selected_month': month,
        'selected_status': status
    }
    
    return render(request, 'student_portal/daily_attendance.html', context)

# Helper functions
def generate_monthly_calendar(student, year, month, subject_id=None):
    """Generate calendar structure for a month with attendance status"""
    # Get the first day of the month
    first_day = datetime.date(year, month, 1)
    
    # Get the last day of the month
    if month == 12:
        last_day = datetime.date(year, month, 31)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    
    # Get the weekday of the first day (0 = Monday, 6 = Sunday)
    first_weekday = first_day.weekday()
    
    # Adjust for Sunday as first day of week
    first_weekday = (first_weekday + 1) % 7
    
    # Generate calendar grid
    calendar_days = []
    
    # Add empty cells for days before the first day of the month
    for _ in range(first_weekday):
        calendar_days.append({'is_empty': True})
    
    # Add days of the month
    current_day = first_day
    today = timezone.now().date()
    
    while current_day <= last_day:
        # Get attendance status for this day
        status = get_day_attendance_status(student, current_day, subject_id)
        
        calendar_days.append({
            'is_empty': False,
            'date': current_day,
            'day': current_day.day,
            'is_today': current_day == today,
            'status': status
        })
        
        current_day += datetime.timedelta(days=1)
    
    # Organize into weeks
    weeks = []
    for i in range(0, len(calendar_days), 7):
        week = calendar_days[i:i+7]
        # If week has fewer than 7 days, add empty cells
        while len(week) < 7:
            week.append({'is_empty': True})
        weeks.append(week)
    
    return weeks

def get_day_attendance_status(student, date, subject_id=None):
    """Get attendance status for a specific day"""
    # Query attendance records for the date
    query = Q(student=student, attendance_date=date)
    
    if subject_id:
        query &= Q(faculty_subject__subject_id=subject_id)
    
    attendance = Attendance.objects.filter(query).first()
    
    if not attendance:
        return None  # No class or record
    
    return attendance.status

def get_detailed_attendance_records(student, subject_id=None, month=None, status=None):
    """Get detailed attendance records with filtering"""
    # Base query
    query = Q(student=student)
    
    # Apply filters
    if subject_id:
        query &= Q(faculty_subject__subject_id=subject_id)
    
    if month:
        try:
            month_num = int(month)
            # Get all dates in the selected month of the current year
            year = timezone.now().year
            query &= Q(attendance_date__month=month_num, attendance_date__year=year)
        except (ValueError, TypeError):
            pass
    
    if status:
        query &= Q(status=status)
    
    # Get records
    records = Attendance.objects.filter(query).select_related(
        'faculty_subject__subject',
        'faculty_subject__faculty__user'
    ).order_by('-attendance_date')
    
    # Format records
    formatted_records = []
    for record in records:
        faculty_subject = record.faculty_subject
        subject = faculty_subject.subject
        faculty = faculty_subject.faculty
        
        record_info = {
            'date': record.attendance_date.strftime('%d %b, %Y'),
            'day': record.attendance_date.strftime('%A'),
            'start_time': '10:00 AM',  # Would come from timetable
            'end_time': '11:00 AM',    # Would come from timetable
            'topic': 'Regular Class',  # Would come from lesson plan
            'faculty_name': faculty.user.full_name,
            'status': record.status,
            'remarks': '',
            'is_lab': faculty_subject.is_lab
        }
        formatted_records.append(record_info)
    
    return formatted_records