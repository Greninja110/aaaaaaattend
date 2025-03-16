from django.db import models
from django.utils import timezone
from authentication.models import User
from core.models import Department, Faculty, Student, SystemLog, ClassSection, Batch
from django.core.validators import MinValueValidator, MaxValueValidator
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


class Subject(models.Model):
    """Subject model for courses offered"""
    subject_id = models.AutoField(primary_key=True)
    subject_code = models.CharField(max_length=20, unique=True, null=False)
    subject_name = models.CharField(max_length=100, null=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    semester = models.IntegerField(null=False, 
                                  validators=[MinValueValidator(1), MaxValueValidator(8)])
    credits = models.IntegerField(null=False)
    has_theory = models.BooleanField(default=True)
    has_lab = models.BooleanField(default=False)
    is_elective = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.subject_code} - {self.subject_name}"
    
    class Meta:
        managed = False  # Don't try to create/modify this table
        db_table = 'subjects'
        

class ElectiveSubject(models.Model):
    """Model for elective subjects"""
    elective_id = models.AutoField(primary_key=True)
    subject = models.OneToOneField(Subject, on_delete=models.CASCADE)
    elective_group = models.CharField(max_length=50, null=False)
    semester = models.IntegerField(null=False, 
                                  validators=[MinValueValidator(5), MaxValueValidator(8)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.subject.subject_name} ({self.elective_group})"
    
    class Meta:
        managed = False
        db_table = 'elective_subjects'
        constraints = [
            models.UniqueConstraint(fields=['subject'], name='unique_subject_elective')
        ]

class FacultySubject(models.Model):
    """Model for mapping faculty to subjects"""
    faculty_subject_id = models.AutoField(primary_key=True)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_section = models.ForeignKey(ClassSection, on_delete=models.CASCADE, null=True, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    is_lab = models.BooleanField(default=False)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        section = f" ({self.class_section})" if self.class_section else ""
        batch = f" Batch {self.batch}" if self.batch else ""
        lab = " (Lab)" if self.is_lab else ""
        return f"{self.faculty.user.full_name} - {self.subject.subject_name}{section}{batch}{lab}"
    
    class Meta:
        managed = False  # Don't create/alter the table - just use the existing one
        db_table = 'faculty_subject'
        constraints = [
            models.UniqueConstraint(
                fields=['faculty', 'subject', 'class_section', 'batch', 'academic_year', 'is_lab'],
                name='unique_faculty_subject_class_batch_year'
            )
        ]