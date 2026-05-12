from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, Sum, Q, F, Case, When, IntegerField
from django.core.paginator import Paginator
from django.db import transaction
from django.urls import reverse
from authentication.models import User, Role
from core.models import (
    Faculty, Student, Department, AcademicYear, ClassSection, Batch,
    Subject, FacultySubject, Attendance, LeaveApplication, Timetable,
    SystemLog
)
from admin_portal.models import BulkImportLog
import json
import logging
import datetime
import csv
import io
from dateutil.relativedelta import relativedelta

# Configure logging
logger = logging.getLogger(__name__)

def faculty_required(view_func):
    """Decorator to check if user has faculty role"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.get_role() != 'faculty':
            logger.warning(f"Unauthorized access attempt to faculty portal by {request.user.email}")
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to access the Faculty Portal.',
                'return_url': '/'
            })
        return view_func(request, *args, **kwargs)
    return wrapper

def get_faculty_for_user(user):
    """Get faculty object for user"""
    try:
        return Faculty.objects.get(user=user)
    except Faculty.DoesNotExist:
        logger.error(f"Faculty record not found for user {user.username}")
        return None

def get_current_academic_year():
    """Get current academic year"""
    try:
        return AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        current_year = timezone.now().year
        academic_year, created = AcademicYear.objects.get_or_create(
            year_start=current_year,
            year_end=current_year + 1,
            defaults={'is_current': True}
        )
        return academic_year

@faculty_required
def index(request):
    """Faculty Dashboard view"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found. Please contact admin.')
        return redirect('login')
    
    academic_year = get_current_academic_year()
    
    # Get faculty's assigned subjects
    faculty_subjects = FacultySubject.objects.filter(
        faculty=faculty,
        academic_year=academic_year
    ).select_related('subject', 'class_section', 'batch')
    
    # Get today's classes
    today = timezone.now().date()
    today_classes = Timetable.objects.filter(
        faculty_subject__in=faculty_subjects,
        day_of_week=today.strftime('%A')
    ).select_related('faculty_subject__subject', 'faculty_subject__class_section')
    
    # Get recent attendance statistics
    attendance_stats = []
    for fs in faculty_subjects:
        students = Student.objects.filter(
            department=fs.subject.department,
            current_semester=fs.subject.semester
        )
        if fs.class_section:
            students = students.filter(class_section=fs.class_section)
        if fs.batch:
            students = students.filter(batch=fs.batch)
        
        total_students = students.count()
        total_classes = Attendance.objects.filter(
            faculty_subject=fs
        ).values('attendance_date').distinct().count()
        
        avg_attendance = 0
        if total_classes > 0:
            present_count = Attendance.objects.filter(
                faculty_subject=fs,
                status='present'
            ).count()
            total_records = Attendance.objects.filter(
                faculty_subject=fs,
                status__in=['present', 'absent']
            ).count()
            if total_records > 0:
                avg_attendance = round((present_count / total_records) * 100, 2)
        
        attendance_stats.append({
            'subject': fs.subject,
            'class_section': fs.class_section,
            'batch': fs.batch,
            'is_lab': fs.is_lab,
            'total_students': total_students,
            'total_classes': total_classes,
            'avg_attendance': avg_attendance
        })
    
    # Get pending leave applications
    pending_leaves = LeaveApplication.objects.filter(
        status='pending',
        student__department=faculty.department
    ).select_related('student__user').order_by('-created_at')[:5]
    
    # Get recent attendance records
    recent_attendance = Attendance.objects.filter(
        faculty_subject__in=faculty_subjects,
        recorded_by=faculty
    ).select_related('student__user', 'faculty_subject__subject').order_by('-recorded_at')[:10]
    
    context = {
        'faculty': faculty,
        'academic_year': academic_year,
        'today_classes': today_classes,
        'attendance_stats': attendance_stats,
        'pending_leaves': pending_leaves,
        'recent_attendance': recent_attendance,
        'faculty_subjects': faculty_subjects,
    }
    
    return render(request, 'faculty_portal/index.html', context)

@faculty_required
def timetable(request):
    """Faculty timetable view"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    academic_year = get_current_academic_year()
    
    # Get faculty's timetable
    timetable_entries = Timetable.objects.filter(
        faculty_subject__faculty=faculty,
        academic_year=academic_year
    ).select_related('faculty_subject__subject', 'faculty_subject__class_section').order_by('day_of_week', 'start_time')
    
    # Organize by day of week
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    timetable_by_day = {day: [] for day in days}
    
    for entry in timetable_entries:
        timetable_by_day[entry.day_of_week].append(entry)
    
    context = {
        'faculty': faculty,
        'academic_year': academic_year,
        'timetable_by_day': timetable_by_day,
        'days': days,
    }
    
    return render(request, 'faculty_portal/timetable.html', context)

@faculty_required
def attendance_record(request):
    """Attendance recording view"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    academic_year = get_current_academic_year()
    
    # Get faculty's assigned subjects
    faculty_subjects = FacultySubject.objects.filter(
        faculty=faculty,
        academic_year=academic_year
    ).select_related('subject', 'class_section', 'batch')
    
    context = {
        'faculty': faculty,
        'academic_year': academic_year,
        'faculty_subjects': faculty_subjects,
    }
    
    return render(request, 'faculty_portal/attendance_record.html', context)

@faculty_required
def record_attendance(request, faculty_subject_id):
    """Record attendance for a specific subject"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    faculty_subject = get_object_or_404(
        FacultySubject, 
        faculty_subject_id=faculty_subject_id,
        faculty=faculty
    )
    
    # Get students for this subject
    students = Student.objects.filter(
        department=faculty_subject.subject.department,
        current_semester=faculty_subject.subject.semester
    ).select_related('user')
    
    if faculty_subject.class_section:
        students = students.filter(class_section=faculty_subject.class_section)
    if faculty_subject.batch:
        students = students.filter(batch=faculty_subject.batch)
    
    # Get today's date
    today = timezone.now().date()
    
    # Check if attendance already recorded for today
    existing_attendance = Attendance.objects.filter(
        faculty_subject=faculty_subject,
        attendance_date=today
    ).exists()
    
    if request.method == 'POST':
        attendance_date = request.POST.get('attendance_date', today)
        
        with transaction.atomic():
            # Delete existing attendance for this date
            Attendance.objects.filter(
                faculty_subject=faculty_subject,
                attendance_date=attendance_date
            ).delete()
            
            # Record new attendance
            attendance_records = []
            for student in students:
                status = request.POST.get(f'attendance_{student.student_id}')
                if status in ['present', 'absent']:
                    attendance_records.append(Attendance(
                        student=student,
                        faculty_subject=faculty_subject,
                        attendance_date=attendance_date,
                        status=status,
                        recorded_by=faculty
                    ))
            
            if attendance_records:
                Attendance.objects.bulk_create(attendance_records)
                
                # Log the action
                SystemLog.objects.create(
                    user=request.user,
                    action=f"Recorded attendance for {faculty_subject.subject.subject_name}",
                    details=f"Date: {attendance_date}, Students: {len(attendance_records)}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Attendance recorded successfully for {len(attendance_records)} students.')
            else:
                messages.warning(request, 'No attendance data was recorded.')
        
        return redirect('faculty_portal:record_attendance', faculty_subject_id=faculty_subject_id)
    
    # Get existing attendance for today
    today_attendance = {}
    if existing_attendance:
        attendance_records = Attendance.objects.filter(
            faculty_subject=faculty_subject,
            attendance_date=today
        )
        today_attendance = {att.student.student_id: att.status for att in attendance_records}
    
    context = {
        'faculty': faculty,
        'faculty_subject': faculty_subject,
        'students': students,
        'today': today,
        'existing_attendance': existing_attendance,
        'today_attendance': today_attendance,
    }
    
    return render(request, 'faculty_portal/record_attendance.html', context)

@faculty_required
def attendance_history(request):
    """View attendance history"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    academic_year = get_current_academic_year()
    
    # Get faculty's assigned subjects
    faculty_subjects = FacultySubject.objects.filter(
        faculty=faculty,
        academic_year=academic_year
    ).select_related('subject', 'class_section', 'batch')
    
    selected_subject = request.GET.get('subject')
    if selected_subject:
        faculty_subjects = faculty_subjects.filter(faculty_subject_id=selected_subject)
    
    # Get attendance records
    attendance_records = Attendance.objects.filter(
        faculty_subject__in=faculty_subjects
    ).select_related('student__user', 'faculty_subject__subject').order_by('-attendance_date', 'student__user__full_name')
    
    # Pagination
    paginator = Paginator(attendance_records, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'faculty': faculty,
        'faculty_subjects': FacultySubject.objects.filter(faculty=faculty, academic_year=academic_year),
        'selected_subject': selected_subject,
        'page_obj': page_obj,
        'attendance_records': page_obj,
    }
    
    return render(request, 'faculty_portal/attendance_history.html', context)

@faculty_required
def leave_applications(request):
    """View and manage leave applications"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    # Get leave applications from faculty's department
    leave_applications = LeaveApplication.objects.filter(
        student__department=faculty.department
    ).select_related('student__user').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        leave_applications = leave_applications.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(leave_applications, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'faculty': faculty,
        'page_obj': page_obj,
        'leave_applications': page_obj,
        'status_filter': status_filter,
    }
    
    return render(request, 'faculty_portal/leave_applications.html', context)

@faculty_required
def approve_leave(request, leave_id):
    """Approve a leave application"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    leave_application = get_object_or_404(
        LeaveApplication,
        leave_id=leave_id,
        student__department=faculty.department
    )
    
    if leave_application.status == 'pending':
        leave_application.status = 'faculty_approved'
        leave_application.faculty_approval = faculty
        leave_application.save()
        
        # Log the action
        SystemLog.objects.create(
            user=request.user,
            action=f"Approved leave application for {leave_application.student.user.full_name}",
            details=f"Leave period: {leave_application.start_date} to {leave_application.end_date}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(request, f'Leave application approved for {leave_application.student.user.full_name}.')
    else:
        messages.warning(request, 'Leave application has already been processed.')
    
    return redirect('faculty_portal:leave_applications')

@faculty_required
def reject_leave(request, leave_id):
    """Reject a leave application"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    leave_application = get_object_or_404(
        LeaveApplication,
        leave_id=leave_id,
        student__department=faculty.department
    )
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        
        if leave_application.status == 'pending':
            leave_application.status = 'rejected'
            leave_application.faculty_approval = faculty
            leave_application.rejection_reason = rejection_reason
            leave_application.save()
            
            # Log the action
            SystemLog.objects.create(
                user=request.user,
                action=f"Rejected leave application for {leave_application.student.user.full_name}",
                details=f"Reason: {rejection_reason}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'Leave application rejected for {leave_application.student.user.full_name}.')
        else:
            messages.warning(request, 'Leave application has already been processed.')
        
        return redirect('faculty_portal:leave_applications')
    
    context = {
        'faculty': faculty,
        'leave_application': leave_application,
    }
    
    return render(request, 'faculty_portal/reject_leave.html', context)

@faculty_required
def reports(request):
    """Generate reports for faculty subjects"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    academic_year = get_current_academic_year()
    
    # Get faculty's assigned subjects
    faculty_subjects = FacultySubject.objects.filter(
        faculty=faculty,
        academic_year=academic_year
    ).select_related('subject', 'class_section', 'batch')
    
    selected_subject = request.GET.get('subject')
    report_type = request.GET.get('type', 'attendance')
    
    reports_data = []
    
    if selected_subject:
        faculty_subject = get_object_or_404(
            FacultySubject,
            faculty_subject_id=selected_subject,
            faculty=faculty
        )
        
        # Get students for this subject
        students = Student.objects.filter(
            department=faculty_subject.subject.department,
            current_semester=faculty_subject.subject.semester
        ).select_related('user')
        
        if faculty_subject.class_section:
            students = students.filter(class_section=faculty_subject.class_section)
        if faculty_subject.batch:
            students = students.filter(batch=faculty_subject.batch)
        
        # Generate attendance report
        for student in students:
            attendance_records = Attendance.objects.filter(
                student=student,
                faculty_subject=faculty_subject,
                status__in=['present', 'absent']
            )
            
            total_classes = attendance_records.count()
            present_classes = attendance_records.filter(status='present').count()
            absent_classes = attendance_records.filter(status='absent').count()
            
            attendance_percentage = 0
            if total_classes > 0:
                attendance_percentage = round((present_classes / total_classes) * 100, 2)
            
            reports_data.append({
                'student': student,
                'total_classes': total_classes,
                'present_classes': present_classes,
                'absent_classes': absent_classes,
                'attendance_percentage': attendance_percentage,
                'below_threshold': attendance_percentage < 75
            })
    
    # Export to CSV if requested
    if request.GET.get('export') == 'csv' and reports_data:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{faculty_subject.subject.subject_code}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Student Name', 'Roll Number', 'Total Classes', 'Present', 'Absent', 'Attendance %', 'Below Threshold'])
        
        for data in reports_data:
            writer.writerow([
                data['student'].user.full_name,
                data['student'].roll_number,
                data['total_classes'],
                data['present_classes'],
                data['absent_classes'],
                data['attendance_percentage'],
                'Yes' if data['below_threshold'] else 'No'
            ])
        
        return response
    
    context = {
        'faculty': faculty,
        'faculty_subjects': faculty_subjects,
        'selected_subject': selected_subject,
        'report_type': report_type,
        'reports_data': reports_data,
    }
    
    return render(request, 'faculty_portal/reports.html', context)

@faculty_required
def bulk_attendance(request):
    """Bulk attendance upload"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    academic_year = get_current_academic_year()
    
    # Get faculty's assigned subjects
    faculty_subjects = FacultySubject.objects.filter(
        faculty=faculty,
        academic_year=academic_year
    ).select_related('subject', 'class_section', 'batch')
    
    if request.method == 'POST':
        uploaded_file = request.FILES.get('attendance_file')
        faculty_subject_id = request.POST.get('faculty_subject')
        
        if not uploaded_file or not faculty_subject_id:
            messages.error(request, 'Please select a file and subject.')
            return redirect('faculty_portal:bulk_attendance')
        
        faculty_subject = get_object_or_404(
            FacultySubject,
            faculty_subject_id=faculty_subject_id,
            faculty=faculty
        )
        
        try:
            # Read CSV file
            file_data = uploaded_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(file_data))
            
            success_count = 0
            error_count = 0
            errors = []
            
            with transaction.atomic():
                for row in csv_reader:
                    try:
                        roll_number = row.get('roll_number', '').strip()
                        attendance_date = datetime.datetime.strptime(row.get('date', ''), '%Y-%m-%d').date()
                        status = row.get('status', '').strip().lower()
                        
                        if status not in ['present', 'absent']:
                            errors.append(f"Invalid status '{status}' for roll number {roll_number}")
                            error_count += 1
                            continue
                        
                        # Find student
                        student = Student.objects.filter(
                            roll_number=roll_number,
                            department=faculty_subject.subject.department,
                            current_semester=faculty_subject.subject.semester
                        ).first()
                        
                        if not student:
                            errors.append(f"Student with roll number {roll_number} not found")
                            error_count += 1
                            continue
                        
                        # Create or update attendance
                        attendance, created = Attendance.objects.update_or_create(
                            student=student,
                            faculty_subject=faculty_subject,
                            attendance_date=attendance_date,
                            defaults={
                                'status': status,
                                'recorded_by': faculty
                            }
                        )
                        
                        success_count += 1
                        
                    except Exception as e:
                        errors.append(f"Error processing row for roll number {roll_number}: {str(e)}")
                        error_count += 1
            
            # Log the action
            SystemLog.objects.create(
                user=request.user,
                action=f"Bulk attendance upload for {faculty_subject.subject.subject_name}",
                details=f"Success: {success_count}, Errors: {error_count}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            if success_count > 0:
                messages.success(request, f'Successfully processed {success_count} attendance records.')
            
            if error_count > 0:
                messages.warning(request, f'{error_count} errors occurred during import.')
                for error in errors[:10]:  # Show first 10 errors
                    messages.error(request, error)
                
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
        
        return redirect('faculty_portal:bulk_attendance')
    
    context = {
        'faculty': faculty,
        'faculty_subjects': faculty_subjects,
    }
    
    return render(request, 'faculty_portal/bulk_attendance.html', context)

@faculty_required
def download_attendance_template(request, faculty_subject_id):
    """Download attendance template CSV"""
    faculty = get_faculty_for_user(request.user)
    if not faculty:
        messages.error(request, 'Faculty profile not found.')
        return redirect('faculty_portal:index')
    
    faculty_subject = get_object_or_404(
        FacultySubject,
        faculty_subject_id=faculty_subject_id,
        faculty=faculty
    )
    
    # Get students for this subject
    students = Student.objects.filter(
        department=faculty_subject.subject.department,
        current_semester=faculty_subject.subject.semester
    ).select_related('user')
    
    if faculty_subject.class_section:
        students = students.filter(class_section=faculty_subject.class_section)
    if faculty_subject.batch:
        students = students.filter(batch=faculty_subject.batch)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_template_{faculty_subject.subject.subject_code}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['roll_number', 'student_name', 'date', 'status'])
    
    today = timezone.now().date()
    for student in students:
        writer.writerow([
            student.roll_number,
            student.user.full_name,
            today.strftime('%Y-%m-%d'),
            'present'  # Default status
        ])
    
    return response