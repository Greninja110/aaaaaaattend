from django.db import models
from django.utils import timezone
from authentication.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Department(models.Model):
    """Department model for institution departments"""
    department_id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=100, null=False)
    department_code = models.CharField(max_length=10, unique=True, null=False)
    hod_id = models.IntegerField(null=True, blank=True)
    # Remove timestamp fields that don't exist in DB
    
    def __str__(self):
        return self.department_name
    
    class Meta:
        # managed = False  # Don't let Django manage this table
        db_table = 'departments'
        
class AcademicYear(models.Model):
    """Academic Year model"""
    academic_year_id = models.AutoField(primary_key=True)
    year_start = models.IntegerField(null=False)
    year_end = models.IntegerField(null=False)
    is_current = models.BooleanField(default=False)
    # Remove timestamp fields if they don't exist
    
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
        # managed = False  # Don't let Django manage this table
        db_table = 'academic_years'

class ClassSection(models.Model):
    """Class Section model for dividing classes into sections"""
    class_section_id = models.AutoField(primary_key=True)
    section_name = models.CharField(max_length=10, null=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True)
    # Remove timestamp fields if they don't exist
    
    def __str__(self):
        department_code = self.department.department_code if self.department else "UNKNOWN"
        return f"{department_code}-{self.section_name}"
    
    class Meta:
        # managed = False  # Don't let Django manage this table
        db_table = 'class_sections'

class Batch(models.Model):
    """Batch model for lab groups"""
    batch_id = models.AutoField(primary_key=True)
    batch_name = models.CharField(max_length=1, unique=True, null=False)
    # Remove timestamp fields if they don't exist
    
    def __str__(self):
        return self.batch_name
    
    class Meta:
        # managed = False  # Don't let Django manage this table
        db_table = 'batches'
        
class SystemLog(models.Model):
    """System log model for tracking activities"""
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    details = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Keep this if it exists in the DB
    
    def __str__(self):
        user_name = str(self.user) if self.user else "Unknown"
        return f"{self.action} by {user_name} at {self.created_at}"
    
    class Meta:
        # managed = False  # Don't let Django manage this table
        db_table = 'system_logs'

class Faculty(models.Model):
    """Faculty model for storing faculty information"""
    faculty_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    employee_id = models.CharField(max_length=20, unique=True, null=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True)
    dob = models.DateField(null=True, blank=True)
    joining_year = models.IntegerField(null=False, default=2023)
    designation = models.CharField(max_length=100, null=False, default="Assistant Professor")
    weekly_hours_limit = models.IntegerField(default=40)
    current_weekly_hours = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='active', 
                             choices=[('active', 'Active'), ('inactive', 'Inactive'), ('on_leave', 'On Leave')])
    # Remove timestamp fields if they don't exist
    
    def __str__(self):
        user_name = self.user.full_name if self.user else "Unknown"
        return f"{user_name} ({self.employee_id})"
    
    class Meta:
        # managed = False  # Don't let Django manage this table
        db_table = 'faculty'

class Student(models.Model):
    """Student model for storing student information"""
    student_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    roll_number = models.CharField(max_length=20, unique=True, null=False)
    admission_year = models.IntegerField(null=False, default=2023)
    dob = models.DateField(null=True, blank=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
    class_section = models.ForeignKey(ClassSection, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True)
    current_semester = models.IntegerField(null=False, default=1,
                                          validators=[MinValueValidator(1), MaxValueValidator(8)])
    section = models.CharField(max_length=5, null=True, blank=True)
    status = models.CharField(max_length=20, default='active', 
                             choices=[('active', 'Active'), ('inactive', 'Inactive'), 
                                     ('graduated', 'Graduated'), ('suspended', 'Suspended')])
    # Remove timestamp fields if they don't exist
    
    def __str__(self):
        user_name = self.user.full_name if self.user else "Unknown"
        return f"{user_name} ({self.roll_number})"
    
    class Meta:
        # managed = False  # Don't let Django manage this table
        db_table = 'students'