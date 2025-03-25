from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
import logging
import os
from core.models import Student  # Adjust this import based on where your Student model is defined
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import time
import os
import time
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage


# Set up logging
logger = logging.getLogger(__name__)
log_file = os.path.join(os.path.dirname(__file__), 'student_portal.log')
file_handler = logging.FileHandler(log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)




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

#logs
@login_required
def log_view(request):

    return render(request, 'student_portal/proflog_viewile.html')






@login_required
@require_POST
def update_skills(request):
    """Update student skills"""
    try:
        skills_list = request.POST.get('skills', '').split(',')
        skills_list = [skill.strip() for skill in skills_list if skill.strip()]
        
        logger.info(f"Updating skills for user {request.user.username}: {skills_list}")
        
        # In a real app, you would update a Student model
        # For now, just returning success
        
        return JsonResponse({
            'success': True,
            'message': 'Skills updated successfully.',
            'skills': skills_list
        })
    except Exception as e:
        logger.error(f"Error updating skills: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error updating skills: {str(e)}"
        })

@login_required
@require_POST
def save_preferences(request):
    """Save user interface preferences"""
    try:
        theme = request.POST.get('theme', 'light')
        default_view = request.POST.get('default_view', 'dashboard')
        enable_notifications = request.POST.get('enable_notifications') == 'on'
        
        logger.info(f"Saving preferences for user {request.user.username}: theme={theme}, view={default_view}")
        
        # In a real app, you would save to a UserPreferences model
        
        # Check if theme changed (would compare to stored value in real app)
        theme_changed = True
        
        return JsonResponse({
            'success': True,
            'theme_changed': theme_changed
        })
    except Exception as e:
        logger.error(f"Error saving preferences: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error saving preferences: {str(e)}"
        })

@login_required
def upload_profile_photo(request):
    """Handle profile photo uploads"""
    try:
        if request.method == 'POST' and request.FILES.get('profile_photo'):
            logger.info(f"Profile photo upload attempt by user {request.user.username}")
            
            # Get the uploaded file
            uploaded_file = request.FILES['profile_photo']
            
            # Validate file size (max 2MB)
            if uploaded_file.size > 2 * 1024 * 1024:
                logger.warning(f"Profile photo upload failed: File too large ({uploaded_file.size} bytes)")
                return JsonResponse({
                    'success': False,
                    'message': 'File size exceeds the 2MB limit.'
                })
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif']
            if uploaded_file.content_type not in allowed_types:
                logger.warning(f"Profile photo upload failed: Invalid file type ({uploaded_file.content_type})")
                return JsonResponse({
                    'success': False,
                    'message': 'Only JPEG, PNG, and GIF images are allowed.'
                })
            
            # Create directory for profile photos
            profile_photos_dir = os.path.join(settings.MEDIA_ROOT, 'profile_photos', str(request.user.id))
            os.makedirs(profile_photos_dir, exist_ok=True)
            
            # Generate unique filename
            file_extension = os.path.splitext(uploaded_file.name)[1]
            filename = f"profile_{request.user.id}_{int(time.time())}{file_extension}"
            
            # Save the file
            fs = FileSystemStorage(location=profile_photos_dir)
            saved_filename = fs.save(filename, uploaded_file)
            
            # In a real app, you would update the Student model profile_photo field
            
            logger.info(f"Profile photo uploaded successfully for user {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'message': 'Profile photo uploaded successfully.',
                'photo_url': f"/media/profile_photos/{request.user.id}/{saved_filename}"
            })
        
        logger.warning(f"Profile photo upload failed: No file provided by user {request.user.username}")
        return JsonResponse({
            'success': False,
            'message': 'No file was uploaded.'
        })
    except Exception as e:
        logger.error(f"Error uploading profile photo: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        })

# Attendance-related views
@login_required
def get_day_attendance(request):
    """Get attendance details for a specific day"""
    try:
        date = request.GET.get('date')
        subject = request.GET.get('subject', '')
        
        logger.info(f"Getting day attendance for user {request.user.username}: date={date}, subject={subject}")
        
        # In a real app, you would query the database for the attendance records
        # For now, returning mock data
        
        # Mock data for attendance detail
        attendance_id = f"{date.replace('-', '')}-{subject}"
        status = "present"  # or "absent" or "leave"
        subject_name = "Sample Subject"
        can_request_correction = True
        
        # Render HTML for detail view
        html_content = """
        <div class="day-detail-status present">
            <i class="fas fa-check-circle me-2"></i> Present
        </div>
        <div class="day-detail-info">
            <h6>Class Details</h6>
            <table class="table table-sm">
                <tr><th>Subject</th><td>Sample Subject</td></tr>
                <tr><th>Topic</th><td>Introduction to Python</td></tr>
                <tr><th>Time</th><td>10:00 AM - 11:00 AM</td></tr>
                <tr><th>Faculty</th><td>Prof. Smith</td></tr>
                <tr><th>Room</th><td>Lab 101</td></tr>
            </table>
        </div>
        """
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'attendance_id': attendance_id,
            'status': status,
            'subject_name': subject_name,
            'can_request_correction': can_request_correction
        })
    except Exception as e:
        logger.error(f"Error getting day attendance: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error retrieving attendance: {str(e)}"
        })

@login_required
@require_POST
def request_attendance_correction(request):
    """Handle attendance correction requests"""
    try:
        attendance_id = request.POST.get('attendance_id', '')
        current_status = request.POST.get('current_status', '')
        requested_status = request.POST.get('requested_status', '')
        reason = request.POST.get('reason', '')
        
        logger.info(f"Attendance correction request from user {request.user.username}: " +
                    f"id={attendance_id}, from={current_status}, to={requested_status}")
        
        # In a real app, you would save this to a correction requests table
        # For now, just log and return success
        
        # Check if evidence was uploaded
        if 'evidence' in request.FILES:
            logger.info(f"Evidence file provided for correction request")
            # Process the file similarly to profile photo
        
        return JsonResponse({
            'success': True,
            'message': 'Your attendance correction request has been submitted successfully.',
            'request_id': f"CR{int(time.time())}"
        })
    except Exception as e:
        logger.error(f"Error submitting correction request: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error submitting correction request: {str(e)}"
        })

@login_required
@require_POST
def export_attendance_history(request):
    """Export attendance history"""
    try:
        export_format = request.POST.get('format', 'PDF')
        
        logger.info(f"Exporting attendance history for user {request.user.username} in {export_format} format")
        
        # In a real app, you would generate and serve the file
        # For now, just return success response
        
        return JsonResponse({
            'success': True,
            'message': f"Attendance history has been exported as {export_format}."
        })
    except Exception as e:
        logger.error(f"Error exporting attendance history: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error exporting attendance history: {str(e)}"
        })

# Notification-related views
@login_required
def get_notification_details(request):
    """Get detailed view of a notification"""
    try:
        notification_id = request.GET.get('notification_id', '')
        
        logger.info(f"Getting notification details for user {request.user.username}: id={notification_id}")
        
        # In a real app, you would query notification by ID
        # For now, returning mock data
        
        is_read = False
        
        # HTML content for the notification detail
        html_content = """
        <div class="notification-detail-header">
            <div class="notification-detail-icon attendance">
                <i class="fas fa-bell"></i>
            </div>
            <div class="notification-detail-title">
                <h5>Attendance Alert</h5>
                <p class="notification-detail-time">March 23, 2025, 10:30 AM</p>
            </div>
        </div>
        <div class="notification-detail-content">
            <p>Your attendance in "Computer Networks" has dropped below 75%. Please ensure you attend upcoming classes.</p>
        </div>
        """
        
        return JsonResponse({
            'success': True,
            'html': html_content,
            'is_read': is_read
        })
    except Exception as e:
        logger.error(f"Error getting notification details: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error retrieving notification details: {str(e)}"
        })

@login_required
@require_POST
def update_notification_settings(request):
    """Update notification preferences"""
    try:
        # Get settings from form
        attendance_emails = request.POST.get('attendance_emails') == 'on'
        leave_emails = request.POST.get('leave_emails') == 'on'
        timetable_emails = request.POST.get('timetable_emails') == 'on'
        system_emails = request.POST.get('system_emails') == 'on'
        
        attendance_inapp = request.POST.get('attendance_inapp') == 'on'
        leave_inapp = request.POST.get('leave_inapp') == 'on'
        timetable_inapp = request.POST.get('timetable_inapp') == 'on'
        system_inapp = request.POST.get('system_inapp') == 'on'
        
        logger.info(f"Updating notification settings for user {request.user.username}")
        
        # In a real app, you would update a NotificationSettings model
        # For now, just return success
        
        return JsonResponse({
            'success': True,
            'message': 'Notification settings updated successfully.'
        })
    except Exception as e:
        logger.error(f"Error updating notification settings: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Error updating notification settings: {str(e)}"
        })