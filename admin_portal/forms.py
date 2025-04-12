from django import forms
from core.models import Department, AcademicYear, ClassSection
from authentication.models import User, Role
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.models import FacultySubject, ElectiveSubject, Subject ,Attendance, LeaveApplication
from .models import AdminSetting, BulkImportLog  # Keep any other models still in admin_portal
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.models import Department, AcademicYear, ClassSection, Batch
from authentication.models import User, Role
from .models import AdminSetting, BulkImportLog
from core.models import FacultySubject, Timetable# Update imports of Subject, FacultySubject, ElectiveSubject
from core.models import Subject, FacultySubject, ElectiveSubject ,Timetable, FacultySubject
# Then use Timetable directly without models. prefix

class AcademicYearForm(forms.ModelForm):
    """Form for managing academic years"""
    class Meta:
        model = AcademicYear
        fields = ['year_start', 'is_current']
        widgets = {
            'year_start': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2099}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
    def clean_year_start(self):
        year_start = self.cleaned_data.get('year_start')
        if year_start < 2000 or year_start > 2099:
            raise forms.ValidationError("Year must be between 2000 and 2099")
        return year_start
        
class DepartmentForm(forms.ModelForm):
    """Form for managing departments"""
    class Meta:
        model = Department
        fields = ['department_name', 'department_code']
        widgets = {
            'department_name': forms.TextInput(attrs={'class': 'form-control'}),
            'department_code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10})
        }
        
    def clean_department_code(self):
        code = self.cleaned_data.get('department_code')
        # Convert to uppercase
        return code.upper()

class AdminSettingsForm(forms.Form):
    """Form for configuring system settings"""
    attendance_threshold = forms.IntegerField(
        min_value=50, 
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    default_password = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    session_timeout = forms.IntegerField(
        min_value=5,
        max_value=60,
        label="Session timeout (minutes)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    enable_email_notifications = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class UserCreationForm(forms.ModelForm):
    """Form for creating new users"""
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        validators=[validate_password]
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = User
        fields = ['email', 'username', 'full_name', 'role', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email.endswith('@mbit.edu.in'):
            raise forms.ValidationError("Email must be a valid MBIT email address ending with @mbit.edu.in")
        return email
    
    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2
    
    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

class UserEditForm(forms.ModelForm):
    """Form for editing existing users"""
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = User
        fields = ['email', 'username', 'full_name', 'role', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email changed and already exists
        if email != self.instance.email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists")
        if not email.endswith('@mbit.edu.in'):
            raise forms.ValidationError("Email must be a valid MBIT email address ending with @mbit.edu.in")
        return email

class UserPasswordChangeForm(forms.Form):
    """Form for changing user password by admin"""
    password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        validators=[validate_password]
    )
    password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

class BulkImportForm(forms.Form):
    """Form for bulk importing users from CSV/Excel"""
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        help_text="Upload CSV or Excel file with user data"
    )
    import_type = forms.ChoiceField(
        choices=[
            ('students', 'Students'),
            ('faculty', 'Faculty'),
            ('lab_assistant', 'Lab Assistant')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file extension
            ext = file.name.split('.')[-1].lower()
            if ext not in ['csv', 'xlsx', 'xls']:
                raise forms.ValidationError("Unsupported file format. Please upload a CSV or Excel file.")
            
            # Check file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File size exceeds 5MB limit.")
            
        return file

class FacultyDetailsForm(forms.Form):
    """Form for additional faculty details"""
    employee_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    designation = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    joining_year = forms.IntegerField(
        min_value=1950,
        max_value=2100,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
class StudentDetailsForm(forms.Form):
    """Form for additional student details"""
    roll_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    admission_year = forms.IntegerField(
        min_value=1950,
        max_value=2100,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    current_semester = forms.IntegerField(
        min_value=1,
        max_value=8,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    class_section = forms.ModelChoiceField(
        queryset=ClassSection.objects.all(), 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

class SubjectForm(forms.ModelForm):
    """Form for managing subjects"""
    class Meta:
        model = Subject
        fields = ['subject_code', 'subject_name', 'department', 'semester', 
                 'credits', 'has_theory', 'has_lab', 'is_elective']
        widgets = {
            'subject_code': forms.TextInput(attrs={'class': 'form-control'}),
            'subject_name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 8 }),
            'credits': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'has_theory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_lab': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_elective': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_subject_code(self):
        code = self.cleaned_data.get('subject_code')
        # Convert to uppercase
        return code.upper()
    
    def clean(self):
        cleaned_data = super().clean()
        has_theory = cleaned_data.get('has_theory')
        has_lab = cleaned_data.get('has_lab')
        
        if not has_theory and not has_lab:
            raise forms.ValidationError("Subject must have either theory, lab, or both.")
        
        return cleaned_data
    
    def clean_semester(self):
        semester = self.cleaned_data.get('semester')
        try:
            semester = int(semester)
            if semester < 1 or semester > 8:
                raise forms.ValidationError("Semester must be between 1 and 8")
            return semester
        except (ValueError, TypeError):
            raise forms.ValidationError("Semester must be a valid integer between 1 and 8")

class ElectiveSubjectForm(forms.ModelForm):
    """Form for managing elective subjects"""
    class Meta:
        model = ElectiveSubject
        fields = ['elective_group', 'semester']
        widgets = {
            'elective_group': forms.TextInput(attrs={'class': 'form-control'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 8})
        }

class FacultySubjectForm(forms.ModelForm):
    """Form for assigning faculty to subjects"""
    class Meta:
        model = FacultySubject
        fields = ['faculty', 'subject', 'class_section', 'batch', 'is_lab', 'academic_year']
        widgets = {
            'faculty': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'class_section': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'is_lab': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If current instance has subject, filter class_section by department
        if self.instance and self.instance.subject_id:
            department = self.instance.subject.department
            self.fields['class_section'].queryset = ClassSection.objects.filter(department=department)
        else:
            self.fields['class_section'].queryset = ClassSection.objects.none()
        
        # Set current academic year as default if creating new assignment
        if not self.instance.pk:
            try:
                current_academic_year = AcademicYear.objects.get(is_current=True)
                self.fields['academic_year'].initial = current_academic_year
            except AcademicYear.DoesNotExist:
                pass
    
    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        is_lab = cleaned_data.get('is_lab')
        batch = cleaned_data.get('batch')
        
        if subject:
            # If assigning to lab but subject doesn't have lab
            if is_lab and not subject.has_lab:
                raise forms.ValidationError("Cannot assign faculty to lab for a subject without lab component.")
            
            # If assigning to theory but subject doesn't have theory
            if not is_lab and not subject.has_theory:
                raise forms.ValidationError("Cannot assign faculty to theory for a subject without theory component.")
            
            # If lab assignment, batch should be provided
            if is_lab and not batch:
                raise forms.ValidationError("Batch must be specified for lab assignments.")
        
        return cleaned_data
    

class TimetableForm(forms.ModelForm):
    """Form for timetable entries"""
    class Meta:
        model = Timetable
        fields = ['faculty_subject', 'day_of_week', 'start_time', 'end_time', 'room_number', 'academic_year']
        widgets = {
            'faculty_subject': forms.Select(attrs={'class': 'form-select'}),
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'})
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        day_of_week = cleaned_data.get('day_of_week')
        room_number = cleaned_data.get('room_number')
        academic_year = cleaned_data.get('academic_year')
        faculty_subject = cleaned_data.get('faculty_subject')
        
        # Validate start/end time
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time")
        
        # Check for room conflicts (same room, same time, same day, same academic year)
        if start_time and end_time and day_of_week and room_number and academic_year:
            conflicts = Timetable.objects.filter(
                day_of_week=day_of_week,
                room_number=room_number,
                academic_year=academic_year
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            # Check for overlapping time
            room_conflicts = conflicts.filter(
                Q(start_time__lt=end_time, end_time__gt=start_time)
            )
            
            if room_conflicts.exists():
                conflict = room_conflicts.first()
                raise forms.ValidationError(
                    f"Room conflict: {room_number} is already booked at this time by "
                    f"{conflict.faculty_subject.faculty.user.full_name} for "
                    f"{conflict.faculty_subject.subject.subject_name}"
                )
        
        # Check for faculty conflicts (same faculty, same time, same day, same academic year)
        if start_time and end_time and day_of_week and faculty_subject and academic_year:
            faculty_id = faculty_subject.faculty_id
            conflicts = Timetable.objects.filter(
                day_of_week=day_of_week,
                academic_year=academic_year,
                faculty_subject__faculty_id=faculty_id
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            # Check for overlapping time
            faculty_conflicts = conflicts.filter(
                Q(start_time__lt=end_time, end_time__gt=start_time)
            )
            
            if faculty_conflicts.exists():
                conflict = faculty_conflicts.first()
                raise forms.ValidationError(
                    f"Faculty conflict: {faculty_subject.faculty.user.full_name} is already assigned at this time for "
                    f"{conflict.faculty_subject.subject.subject_name} in room {conflict.room_number}"
                )
        
        return cleaned_data