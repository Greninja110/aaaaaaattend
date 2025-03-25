from django.db import models
from authentication.models import User
from core.models import Student, Faculty, Subject, FacultySubject, Attendance, LeaveApplication
# Create your models here.
# Create models needed for views


class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    message = models.TextField()
    category = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class StudentProfile(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    profile_photo = models.CharField(max_length=255, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, null=True, blank=True)
    skills = models.JSONField(null=True, blank=True)
    linkedin_profile = models.URLField(null=True, blank=True)
    github_profile = models.URLField(null=True, blank=True)
    twitter_profile = models.URLField(null=True, blank=True)
    instagram_profile = models.URLField(null=True, blank=True)
    father_name = models.CharField(max_length=100, null=True, blank=True)
    father_occupation = models.CharField(max_length=100, null=True, blank=True)
    father_contact = models.CharField(max_length=15, null=True, blank=True)
    mother_name = models.CharField(max_length=100, null=True, blank=True)
    mother_occupation = models.CharField(max_length=100, null=True, blank=True)
    mother_contact = models.CharField(max_length=15, null=True, blank=True)
    emergency_contact = models.CharField(max_length=15, null=True, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, null=True, blank=True)

class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    theme = models.CharField(max_length=20, default='light')
    default_view = models.CharField(max_length=20, default='dashboard')
    enable_notifications = models.BooleanField(default=True)

class NotificationSetting(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    attendance_emails = models.BooleanField(default=True)
    leave_emails = models.BooleanField(default=True)
    timetable_emails = models.BooleanField(default=True)
    system_emails = models.BooleanField(default=True)
    attendance_inapp = models.BooleanField(default=True)
    leave_inapp = models.BooleanField(default=True)
    timetable_inapp = models.BooleanField(default=True)
    system_inapp = models.BooleanField(default=True)

class AttendanceCorrectionRequest(models.Model):
    request_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    current_status = models.CharField(max_length=20)
    requested_status = models.CharField(max_length=20)
    reason = models.TextField()
    evidence_path = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    faculty_comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)