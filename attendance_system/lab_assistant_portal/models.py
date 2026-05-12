from django.db import models
from django.utils import timezone
from authentication.models import User

class LabAssistant(models.Model):
    """Lab Assistant model for storing lab assistant information"""
    assistant_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    department = models.ForeignKey('core.Department', on_delete=models.CASCADE, null=True)
    dob = models.DateField(null=True, blank=True)
    joining_year = models.IntegerField(null=False, default=2023)
    status = models.CharField(max_length=20, default='active', 
                             choices=[('active', 'Active'), ('inactive', 'Inactive'), ('on_leave', 'On Leave')])
    
    def __str__(self):
        user_name = self.user.full_name if self.user else "Unknown"
        return f"{user_name}"
    
    class Meta:
        db_table = 'lab_assistant'


class AttendanceException(models.Model):
    """Attendance Exception model for managing attendance corrections"""
    exception_id = models.AutoField(primary_key=True)
    attendance = models.ForeignKey('core.Attendance', on_delete=models.CASCADE)
    requested_by = models.ForeignKey('core.Faculty', on_delete=models.CASCADE, related_name='exception_requests')
    reason = models.TextField()
    previous_status = models.CharField(max_length=20)
    requested_status = models.CharField(max_length=20, choices=[('present', 'Present'), ('absent', 'Absent'), ('dont_care', 'Don\'t Care')])
    status = models.CharField(max_length=20, default='pending',
                             choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    lab_assistant = models.ForeignKey(LabAssistant, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_exception'


class LabIssue(models.Model):
    """Model for tracking lab issues"""
    issue_id = models.AutoField(primary_key=True)
    lab_name = models.CharField(max_length=100)
    issue_type = models.CharField(max_length=50, choices=[
        ('hardware', 'Hardware Issue'),
        ('software', 'Software Issue'),
        ('network', 'Network Issue'),
        ('environment', 'Environmental Issue'),
        ('other', 'Other Issue')
    ])
    description = models.TextField()
    reported_by = models.ForeignKey(LabAssistant, on_delete=models.CASCADE, related_name='reported_issues')
    reported_at = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], default='medium')
    status = models.CharField(max_length=20, choices=[
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved')
    ], default='open')
    resolved_by = models.ForeignKey(LabAssistant, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_issues')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.lab_name} - {self.issue_type} ({self.status})"


class ScheduledReport(models.Model):
    """Model for scheduled reports"""
    report_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=50, choices=[
        ('attendance', 'Attendance'),
        ('leave', 'Leave'),
        ('lab_usage', 'Lab Usage'),
        ('low_attendance', 'Low Attendance')
    ])
    frequency = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ])
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField()
    format = models.CharField(max_length=10, choices=[
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel')
    ], default='pdf')
    recipients = models.TextField()  # Comma-separated list of email addresses
    filters = models.TextField(null=True, blank=True)  # JSON formatted filters
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('paused', 'Paused')
    ], default='active')
    created_by = models.ForeignKey(LabAssistant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name