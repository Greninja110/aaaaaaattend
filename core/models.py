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


# Add these models to core/models.py

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
        db_table = 'faculty_subject'
        constraints = [
            models.UniqueConstraint(
                fields=['faculty', 'subject', 'class_section', 'batch', 'academic_year', 'is_lab'],
                name='unique_faculty_subject_class_batch_year'
            )
        ]

class Timetable(models.Model):
    """Timetable model for scheduling classes"""
    timetable_id = models.AutoField(primary_key=True)
    faculty_subject = models.ForeignKey(FacultySubject, on_delete=models.CASCADE)
    day_of_week = models.CharField(max_length=10, choices=[
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday')
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_number = models.CharField(max_length=20)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.faculty_subject.subject.subject_name} - {self.day_of_week} ({self.start_time} to {self.end_time})"
    
    class Meta:
        db_table = 'timetable'
        constraints = [
            models.UniqueConstraint(
                fields=['room_number', 'start_time', 'day_of_week', 'academic_year'],
                name='unique_room_time_day'
            ),
            models.UniqueConstraint(
                fields=['faculty_subject', 'start_time', 'day_of_week', 'academic_year'],
                name='unique_faculty_time_day'
            )
        ]

class Attendance(models.Model):
    """Attendance model for tracking student attendance"""
    attendance_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    faculty_subject = models.ForeignKey(FacultySubject, on_delete=models.CASCADE)
    attendance_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('present', 'Present'), ('absent', 'Absent'), ('dont_care', 'Don\'t Care')])
    recorded_by = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    recorded_at = models.DateTimeField(auto_now_add=True)
    is_substitution = models.BooleanField(default=False)
    substitution_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'attendance'
        unique_together = ('student', 'faculty_subject', 'attendance_date')

class LeaveApplication(models.Model):
    """Leave Application model for student leave requests"""
    leave_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    document_path = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending',
                             choices=[('pending', 'Pending'), ('faculty_approved', 'Faculty Approved'), 
                                      ('lab_approved', 'Lab Assistant Approved'), ('rejected', 'Rejected')])
    faculty_approval = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name='faculty_approvals')
    lab_assistant_approval = models.ForeignKey('lab_assistant_portal.LabAssistant', on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_approvals')    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'leave_application'
