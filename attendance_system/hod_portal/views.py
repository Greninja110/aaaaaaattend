from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q, F, Case, When, IntegerField, Avg
from django.core.paginator import Paginator
from django.db import transaction
from authentication.models import User, Role
from core.models import (
    Faculty, Student, Department, AcademicYear, ClassSection, Batch,
    Subject, FacultySubject, Attendance, LeaveApplication, Timetable,
    SystemLog
)
from core.models import ElectiveSubject
import json
import logging
import datetime
import csv
import io
from dateutil.relativedelta import relativedelta

# Configure logging
logger = logging.getLogger(__name__)

def hod_required(view_func):
    """Decorator to check if user has HOD role"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.get_role() != 'hod':
            logger.warning(f"Unauthorized access attempt to HOD portal by {request.user.email}")
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to access the HOD Portal.',
                'return_url': '/'
            })
        return view_func(request, *args, **kwargs)
    return wrapper

def get_hod_department(user):
    """Get department where user is HOD"""
    try:
        faculty = Faculty.objects.get(user=user)
        department = Department.objects.get(hod_id=faculty.faculty_id)
        return department
    except (Faculty.DoesNotExist, Department.DoesNotExist):
        logger.error(f"HOD department not found for user {user.username}")
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

@hod_required
def index(request):
    """HOD Dashboard view"""
    department = get_hod_department(request.user)
    if not department:
        messages.error(request, 'You are not assigned as HOD of any department.')
        return redirect('login')
    
    academic_year = get_current_academic_year()
    
    # Get department statistics
    faculty_count = Faculty.objects.filter(department=department, status='active').count()
    students_count = Student.objects.filter(department=department, status='active').count()
    subjects_count = Subject.objects.filter(department=department).count()
    
    # Get students by semester
    students_by_semester = []
    for semester in range(1, 9):
        count = Student.objects.filter(
            department=department,
            current_semester=semester,
            status='active'
        ).count()
        students_by_semester.append({
            'semester': semester,
            'count': count
        })
    
    # Get subject-wise attendance statistics
    subject_attendance = []
    department_subjects = Subject.objects.filter(department=department)
    
    for subject in department_subjects:
        faculty_subjects = FacultySubject.objects.filter(
            subject=subject,
            academic_year=academic_year
        )
        
        if faculty_subjects.exists():
            total_records = Attendance.objects.filter(
                faculty_subject__in=faculty_subjects,
                status__in=['present', 'absent']
            ).count()
            
            present_records = Attendance.objects.filter(
                faculty_subject__in=faculty_subjects,
                status='present'
            ).count()
            
            attendance_percentage = 0
            if total_records > 0:
                attendance_percentage = round((present_records / total_records) * 100, 2)
            
            subject_attendance.append({
                'subject': subject,
                'attendance_percentage': attendance_percentage,
                'total_records': total_records,
                'below_threshold': attendance_percentage < 75
            })
    
    # Get low attendance students
    low_attendance_students = []
    for student in Student.objects.filter(department=department, status='active')[:10]:
        student_subjects = FacultySubject.objects.filter(
            subject__department=department,
            subject__semester=student.current_semester,
            academic_year=academic_year
        )
        
        total_records = Attendance.objects.filter(
            student=student,
            faculty_subject__in=student_subjects,
            status__in=['present', 'absent']
        ).count()
        
        present_records = Attendance.objects.filter(
            student=student,
            faculty_subject__in=student_subjects,
            status='present'
        ).count()
        
        if total_records > 0:
            attendance_percentage = round((present_records / total_records) * 100, 2)
            if attendance_percentage < 75:
                low_attendance_students.append({
                    'student': student,
                    'attendance_percentage': attendance_percentage,
                    'total_classes': total_records
                })
    
    # Get faculty workload
    faculty_workload = []
    for faculty in Faculty.objects.filter(department=department, status='active'):
        assigned_subjects = FacultySubject.objects.filter(
            faculty=faculty,
            academic_year=academic_year
        ).count()
        
        timetable_hours = Timetable.objects.filter(
            faculty_subject__faculty=faculty,
            academic_year=academic_year
        ).count()
        
        faculty_workload.append({
            'faculty': faculty,
            'assigned_subjects': assigned_subjects,
            'weekly_hours': timetable_hours,
            'utilization': round((timetable_hours / faculty.weekly_hours_limit) * 100, 2) if faculty.weekly_hours_limit > 0 else 0
        })
    
    # Get recent activities
    recent_activities = SystemLog.objects.filter(
        user__faculty__department=department
    ).select_related('user').order_by('-created_at')[:10]
    
    context = {
        'department': department,
        'academic_year': academic_year,
        'faculty_count': faculty_count,
        'students_count': students_count,
        'subjects_count': subjects_count,
        'students_by_semester': students_by_semester,
        'subject_attendance': subject_attendance,
        'low_attendance_students': low_attendance_students,
        'faculty_workload': faculty_workload,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'hod_portal/index.html', context)

@hod_required
def department_reports(request):
    """Department-wide reports"""
    department = get_hod_department(request.user)
    if not department:
        messages.error(request, 'Department not found.')
        return redirect('hod_portal:index')
    
    academic_year = get_current_academic_year()
    report_type = request.GET.get('type', 'attendance')
    semester_filter = request.GET.get('semester')
    subject_filter = request.GET.get('subject')
    
    reports_data = []
    
    if report_type == 'attendance':
        # Attendance report
        students = Student.objects.filter(
            department=department,
            status='active'
        ).select_related('user')
        
        if semester_filter:
            students = students.filter(current_semester=semester_filter)
        
        for student in students:
            student_subjects = FacultySubject.objects.filter(
                subject__department=department,
                subject__semester=student.current_semester,
                academic_year=academic_year
            )
            
            if subject_filter:
                student_subjects = student_subjects.filter(subject_id=subject_filter)
            
            total_records = Attendance.objects.filter(
                student=student,
                faculty_subject__in=student_subjects,
                status__in=['present', 'absent']
            ).count()
            
            present_records = Attendance.objects.filter(
                student=student,
                faculty_subject__in=student_subjects,
                status='present'
            ).count()
            
            attendance_percentage = 0
            if total_records > 0:
                attendance_percentage = round((present_records / total_records) * 100, 2)
            
            reports_data.append({
                'student': student,
                'total_classes': total_records,
                'present_classes': present_records,
                'absent_classes': total_records - present_records,
                'attendance_percentage': attendance_percentage,
                'below_threshold': attendance_percentage < 75
            })
    
    elif report_type == 'faculty_workload':
        # Faculty workload report
        faculty_members = Faculty.objects.filter(
            department=department,
            status='active'
        ).select_related('user')
        
        for faculty in faculty_members:
            assigned_subjects = FacultySubject.objects.filter(
                faculty=faculty,
                academic_year=academic_year
            )
            
            if subject_filter:
                assigned_subjects = assigned_subjects.filter(subject_id=subject_filter)
            
            subject_count = assigned_subjects.count()
            
            # Calculate weekly hours from timetable
            weekly_hours = Timetable.objects.filter(
                faculty_subject__in=assigned_subjects
            ).count()
            
            utilization = 0
            if faculty.weekly_hours_limit > 0:
                utilization = round((weekly_hours / faculty.weekly_hours_limit) * 100, 2)
            
            reports_data.append({
                'faculty': faculty,
                'assigned_subjects': subject_count,
                'weekly_hours': weekly_hours,
                'hours_limit': faculty.weekly_hours_limit,
                'utilization': utilization,
                'overloaded': weekly_hours > faculty.weekly_hours_limit
            })
    
    # Export to CSV if requested
    if request.GET.get('export') == 'csv' and reports_data:
        response = HttpResponse(content_type='text/csv')
        
        if report_type == 'attendance':
            response['Content-Disposition'] = f'attachment; filename="attendance_report_{department.department_code}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Student Name', 'Roll Number', 'Semester', 'Total Classes', 'Present', 'Absent', 'Attendance %', 'Below Threshold'])
            
            for data in reports_data:
                writer.writerow([
                    data['student'].user.full_name,
                    data['student'].roll_number,
                    data['student'].current_semester,
                    data['total_classes'],
                    data['present_classes'],
                    data['absent_classes'],
                    data['attendance_percentage'],
                    'Yes' if data['below_threshold'] else 'No'
                ])
        
        elif report_type == 'faculty_workload':
            response['Content-Disposition'] = f'attachment; filename="faculty_workload_{department.department_code}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Faculty Name', 'Employee ID', 'Assigned Subjects', 'Weekly Hours', 'Hours Limit', 'Utilization %', 'Overloaded'])
            
            for data in reports_data:
                writer.writerow([
                    data['faculty'].user.full_name,
                    data['faculty'].employee_id,
                    data['assigned_subjects'],
                    data['weekly_hours'],
                    data['hours_limit'],
                    data['utilization'],
                    'Yes' if data['overloaded'] else 'No'
                ])
        
        return response
    
    # Get filter options
    semesters = range(1, 9)
    subjects = Subject.objects.filter(department=department)
    
    context = {
        'department': department,
        'academic_year': academic_year,
        'report_type': report_type,
        'semester_filter': semester_filter,
        'subject_filter': subject_filter,
        'reports_data': reports_data,
        'semesters': semesters,
        'subjects': subjects,
    }
    
    return render(request, 'hod_portal/department_reports.html', context)

@hod_required
def student_progression(request):
    """Manage student semester progression"""
    department = get_hod_department(request.user)
    if not department:
        messages.error(request, 'Department not found.')
        return redirect('hod_portal:index')
    
    academic_year = get_current_academic_year()
    semester_filter = request.GET.get('semester')
    
    # Get students eligible for progression
    students = Student.objects.filter(
        department=department,
        status='active'
    ).select_related('user')
    
    if semester_filter:
        students = students.filter(current_semester=semester_filter)
    
    progression_data = []
    
    for student in students:
        # Calculate overall attendance for current semester
        student_subjects = FacultySubject.objects.filter(
            subject__department=department,
            subject__semester=student.current_semester,
            academic_year=academic_year
        )
        
        total_records = Attendance.objects.filter(
            student=student,
            faculty_subject__in=student_subjects,
            status__in=['present', 'absent']
        ).count()
        
        present_records = Attendance.objects.filter(
            student=student,
            faculty_subject__in=student_subjects,
            status='present'
        ).count()
        
        attendance_percentage = 0
        if total_records > 0:
            attendance_percentage = round((present_records / total_records) * 100, 2)
        
        # Check eligibility (75% attendance)
        eligible = attendance_percentage >= 75
        
        progression_data.append({
            'student': student,
            'current_semester': student.current_semester,
            'attendance_percentage': attendance_percentage,
            'total_classes': total_records,
            'eligible': eligible,
            'can_promote': eligible and student.current_semester < 8
        })
    
    if request.method == 'POST':
        action = request.POST.get('action')
        student_ids = request.POST.getlist('student_ids')
        
        if action == 'promote' and student_ids:
            promoted_count = 0
            
            with transaction.atomic():
                for student_id in student_ids:
                    student = get_object_or_404(Student, student_id=student_id, department=department)
                    
                    # Check if student is eligible
                    student_data = next((item for item in progression_data if item['student'].student_id == int(student_id)), None)
                    
                    if student_data and student_data['can_promote']:
                        # Promote student
                        student.current_semester += 1
                        student.save()
                        
                        # Log the action
                        SystemLog.objects.create(
                            user=request.user,
                            action=f"Promoted student {student.user.full_name} to semester {student.current_semester}",
                            details=f"Previous semester: {student.current_semester - 1}",
                            ip_address=request.META.get('REMOTE_ADDR')
                        )
                        
                        promoted_count += 1
            
            messages.success(request, f'Successfully promoted {promoted_count} students.')
            return redirect('hod_portal:student_progression')
    
    # Pagination
    paginator = Paginator(progression_data, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'department': department,
        'academic_year': academic_year,
        'semester_filter': semester_filter,
        'semesters': range(1, 8),  # Only 1-7 can be promoted
        'page_obj': page_obj,
        'progression_data': page_obj,
    }
    
    return render(request, 'hod_portal/student_progression.html', context)

@hod_required
def elective_management(request):
    """Manage elective subjects"""
    department = get_hod_department(request.user)
    if not department:
        messages.error(request, 'Department not found.')
        return redirect('hod_portal:index')
    
    # Get elective subjects for the department
    elective_subjects = ElectiveSubject.objects.filter(
        subject__department=department
    ).select_related('subject').order_by('semester', 'elective_group')
    
    # Get enrollment statistics
    elective_stats = []
    for elective in elective_subjects:
        # This would be implemented when student elective selection is added
        enrollment_count = 0  # Placeholder
        
        elective_stats.append({
            'elective': elective,
            'enrollment_count': enrollment_count,
            'subject': elective.subject
        })
    
    context = {
        'department': department,
        'elective_stats': elective_stats,
    }
    
    return render(request, 'hod_portal/elective_management.html', context)

@hod_required
def faculty_performance(request):
    """Monitor faculty performance"""
    department = get_hod_department(request.user)
    if not department:
        messages.error(request, 'Department not found.')
        return redirect('hod_portal:index')
    
    academic_year = get_current_academic_year()
    
    faculty_performance = []
    
    for faculty in Faculty.objects.filter(department=department, status='active'):
        # Get assigned subjects
        faculty_subjects = FacultySubject.objects.filter(
            faculty=faculty,
            academic_year=academic_year
        )
        
        # Calculate teaching hours
        weekly_hours = Timetable.objects.filter(
            faculty_subject__in=faculty_subjects
        ).count()
        
        # Get attendance recording rate
        total_scheduled_classes = 0
        recorded_classes = 0
        
        for fs in faculty_subjects:
            # This is a simplified calculation
            # In reality, you'd need to check against actual scheduled classes
            total_scheduled_classes += 30  # Assume 30 classes per subject per semester
            recorded_classes += Attendance.objects.filter(
                faculty_subject=fs,
                recorded_by=faculty
            ).values('attendance_date').distinct().count()
        
        recording_rate = 0
        if total_scheduled_classes > 0:
            recording_rate = round((recorded_classes / total_scheduled_classes) * 100, 2)
        
        # Get average attendance in faculty's classes
        avg_attendance = 0
        total_attendance_records = Attendance.objects.filter(
            faculty_subject__in=faculty_subjects,
            status__in=['present', 'absent']
        ).count()
        
        present_records = Attendance.objects.filter(
            faculty_subject__in=faculty_subjects,
            status='present'
        ).count()
        
        if total_attendance_records > 0:
            avg_attendance = round((present_records / total_attendance_records) * 100, 2)
        
        faculty_performance.append({
            'faculty': faculty,
            'assigned_subjects': faculty_subjects.count(),
            'weekly_hours': weekly_hours,
            'hours_utilization': round((weekly_hours / faculty.weekly_hours_limit) * 100, 2) if faculty.weekly_hours_limit > 0 else 0,
            'recording_rate': recording_rate,
            'avg_attendance': avg_attendance,
            'performance_score': round((recording_rate + avg_attendance) / 2, 2)
        })
    
    # Sort by performance score
    faculty_performance.sort(key=lambda x: x['performance_score'], reverse=True)
    
    context = {
        'department': department,
        'academic_year': academic_year,
        'faculty_performance': faculty_performance,
    }
    
    return render(request, 'hod_portal/faculty_performance.html', context)

@hod_required
def attendance_analytics(request):
    """Advanced attendance analytics"""
    department = get_hod_department(request.user)
    if not department:
        messages.error(request, 'Department not found.')
        return redirect('hod_portal:index')
    
    academic_year = get_current_academic_year()
    
    # Overall department attendance
    dept_subjects = FacultySubject.objects.filter(
        subject__department=department,
        academic_year=academic_year
    )
    
    total_records = Attendance.objects.filter(
        faculty_subject__in=dept_subjects,
        status__in=['present', 'absent']
    ).count()
    
    present_records = Attendance.objects.filter(
        faculty_subject__in=dept_subjects,
        status='present'
    ).count()
    
    overall_attendance = 0
    if total_records > 0:
        overall_attendance = round((present_records / total_records) * 100, 2)
    
    # Semester-wise attendance
    semester_attendance = []
    for semester in range(1, 9):
        sem_subjects = dept_subjects.filter(subject__semester=semester)
        
        sem_total = Attendance.objects.filter(
            faculty_subject__in=sem_subjects,
            status__in=['present', 'absent']
        ).count()
        
        sem_present = Attendance.objects.filter(
            faculty_subject__in=sem_subjects,
            status='present'
        ).count()
        
        sem_percentage = 0
        if sem_total > 0:
            sem_percentage = round((sem_present / sem_total) * 100, 2)
        
        semester_attendance.append({
            'semester': semester,
            'attendance_percentage': sem_percentage,
            'total_records': sem_total
        })
    
    # Subject-wise attendance
    subject_attendance = []
    for subject in Subject.objects.filter(department=department):
        subj_faculty_subjects = dept_subjects.filter(subject=subject)
        
        subj_total = Attendance.objects.filter(
            faculty_subject__in=subj_faculty_subjects,
            status__in=['present', 'absent']
        ).count()
        
        subj_present = Attendance.objects.filter(
            faculty_subject__in=subj_faculty_subjects,
            status='present'
        ).count()
        
        subj_percentage = 0
        if subj_total > 0:
            subj_percentage = round((subj_present / subj_total) * 100, 2)
        
        subject_attendance.append({
            'subject': subject,
            'attendance_percentage': subj_percentage,
            'total_records': subj_total,
            'below_threshold': subj_percentage < 75
        })
    
    # Monthly trend (last 6 months)
    monthly_trend = []
    for i in range(6):
        month_start = timezone.now().date().replace(day=1) - relativedelta(months=i)
        month_end = month_start + relativedelta(months=1) - relativedelta(days=1)
        
        month_total = Attendance.objects.filter(
            faculty_subject__in=dept_subjects,
            attendance_date__range=[month_start, month_end],
            status__in=['present', 'absent']
        ).count()
        
        month_present = Attendance.objects.filter(
            faculty_subject__in=dept_subjects,
            attendance_date__range=[month_start, month_end],
            status='present'
        ).count()
        
        month_percentage = 0
        if month_total > 0:
            month_percentage = round((month_present / month_total) * 100, 2)
        
        monthly_trend.append({
            'month': month_start.strftime('%B %Y'),
            'attendance_percentage': month_percentage,
            'total_records': month_total
        })
    
    monthly_trend.reverse()  # Show oldest to newest
    
    context = {
        'department': department,
        'academic_year': academic_year,
        'overall_attendance': overall_attendance,
        'total_records': total_records,
        'semester_attendance': semester_attendance,
        'subject_attendance': subject_attendance,
        'monthly_trend': monthly_trend,
    }
    
    return render(request, 'hod_portal/attendance_analytics.html', context)