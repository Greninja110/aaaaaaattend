from django.db import models
from django.db import models
from django.utils import timezone
from authentication.models import User

class Department(models.Model):
    """Department model for institution departments"""
    department_id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=100, null=False)
    department_code = models.CharField(max_length=10, unique=True, null=False)
    hod_id = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return self.department_name
    
    class Meta:
        db_table = 'departments'

class Department(models.Model):
    """Department model for institution departments"""
    department_id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=100, null=False)
    department_code = models.CharField(max_length=10, unique=True, null=False)
    hod_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.department_name
    
    class Meta:
        db_table = 'departments'
        
class AcademicYear(models.Model):
    """Academic Year model"""
    academic_year_id = models.AutoField(primary_key=True)
    year_start = models.IntegerField(null=False)
    year_end = models.IntegerField(null=False)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.year_start}-{self.year_end}"
    
    def save(self, *args, **kwargs):
        # Ensure year_end is always year_start + 1
        self.year_end = self.year_start + 1
        
        # If this academic year is marked as current, unmark all others
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).update(is_current=False)
            
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'academic_years'
        constraints = [
            models.UniqueConstraint(fields=['year_start', 'year_end'], name='unique_academic_year'),
            models.CheckConstraint(check=models.Q(year_end=models.F('year_start') + 1), name='valid_year_range')
        ]
        
class ClassSection(models.Model):
    """Class Section model for dividing classes into sections"""
    class_section_id = models.AutoField(primary_key=True)
    section_name = models.CharField(max_length=10, null=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.department.department_code}-{self.section_name}"
    
    class Meta:
        db_table = 'class_sections'
        constraints = [
            models.UniqueConstraint(fields=['section_name', 'department'], name='unique_section_dept')
        ]

class Batch(models.Model):
    """Batch model for lab groups"""
    batch_id = models.AutoField(primary_key=True)
    batch_name = models.CharField(max_length=1, unique=True, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.batch_name
    
    class Meta:
        db_table = 'batches'
        
class SystemLog(models.Model):
    """System log model for tracking activities"""
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    details = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} by {self.user} at {self.created_at}"
    
    class Meta:
        db_table = 'system_logs'