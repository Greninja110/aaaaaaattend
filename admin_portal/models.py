from django.db import models
from django.utils import timezone
from authentication.models import User
from core.models import Department, Faculty, Student, SystemLog, ClassSection, Batch
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import Subject, FacultySubject, Attendance, LeaveApplication
from core.models import AcademicYear

class AdminSetting(models.Model):
    """Model for storing admin configurable settings"""
    setting_id = models.AutoField(primary_key=True)
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField()
    is_public = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_settings')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_settings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.setting_key
    
    class Meta:
        db_table = 'admin_settings'

class BulkImportLog(models.Model):
    """Model for tracking bulk import operations"""
    import_id = models.AutoField(primary_key=True)
    import_type = models.CharField(max_length=50)  # e.g., "students", "faculty"
    file_name = models.CharField(max_length=255)
    total_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    error_details = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.import_type} import by {self.user} on {self.created_at}"
    
    class Meta:
        db_table = 'bulk_import_logs'

