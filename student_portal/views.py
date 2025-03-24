from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role

# Dashboard
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
    
    return render(request, 'student_portal/index.html')


# Attendance
@login_required
def attendance(request):

    return render(request, 'student_portal/attendance.html')

@login_required
def subject_attendance(request):

    return render(request, 'student_portal/subject_attendance.html')

@login_required
def attendance_history(request):

    return render(request, 'student_portal/attendance_history.html')


# Timetable
@login_required
def timetable(request):

    return render(request, 'student_portal/timetable.html')

@login_required
def day_timetable(request):

    return render(request, 'student_portal/day_timetable.html')


# Leave Applications
@login_required
def leave_application(request):

    return render(request, 'student_portal/leave_application.html')

@login_required
def create_leave_application(request):

    return render(request, 'student_portal/leave_application.html')

@login_required
def leave_application_detail(request):

    return render(request, 'student_portal/leave_application.html')

@login_required
def cancel_leave_application(request):

    return render(request, 'student_portal/cancel_leave_application.html')


  # Notifications
@login_required
def notifications(request):

    return render(request, 'student_portal/notifications.html')

@login_required
def mark_notification_read(request):

    return render(request, 'student_portal/notifications.html')

@login_required
def mark_all_notifications_read(request):

    return render(request, 'student_portal/notifications.html')


# Profile
@login_required
def profile(request):

    return render(request, 'student_portal/profile.html')

@login_required
def change_password(request):

    return render(request, 'student_portal/profile.html')

@login_required
def edit_profile(request):

    return render(request, 'student_portal/profile.html')