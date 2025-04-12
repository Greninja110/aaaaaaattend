from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# Import ONLY the models you define in lab_assistant_portal
from .models import AttendanceException, LabIssue, ScheduledReport

# Import core models explicitly - remove any duplicates
from core.models import (
    Subject, FacultySubject, ElectiveSubject, 
    Attendance, LeaveApplication
)


class DateInput(forms.DateInput):
    input_type = 'date'

class LeaveApplicationApprovalForm(forms.ModelForm):
    """Form for approving or rejecting leave applications"""
    comments = forms.CharField(widget=forms.Textarea, required=False)
    
    class Meta:
        model = LeaveApplication
        fields = ['status', 'comments']
        widgets = {
            'status': forms.Select(choices=[
                ('faculty_approved', 'Approve'),
                ('rejected', 'Reject')
            ])
        }

class AttendanceExceptionForm(forms.ModelForm):
    """Form for creating attendance exceptions"""
    class Meta:
        model = AttendanceException
        fields = ['attendance', 'requested_by', 'reason', 'requested_status']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
            'requested_status': forms.Select
        }

class AttendanceExceptionApprovalForm(forms.ModelForm):
    """Form for approving or rejecting attendance exceptions"""
    comments = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    
    class Meta:
        model = AttendanceException
        fields = ['status', 'comments']
        widgets = {
            'status': forms.Select(choices=[
                ('approved', 'Approve'),
                ('rejected', 'Reject')
            ])
        }

class LabIssueForm(forms.ModelForm):
    """Form for reporting lab issues"""
    class Meta:
        model = LabIssue
        fields = ['lab_name', 'issue_type', 'description', 'priority']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'priority': forms.Select
        }

class LabIssueResolutionForm(forms.ModelForm):
    """Form for resolving lab issues"""
    class Meta:
        model = LabIssue
        fields = ['status', 'resolution_notes']
        widgets = {
            'resolution_notes': forms.Textarea(attrs={'rows': 4})
        }

class ScheduledReportForm(forms.ModelForm):
    """Form for scheduling reports"""
    department = forms.ChoiceField(required=False)
    batch = forms.ChoiceField(required=False)
    subject = forms.ChoiceField(required=False)
    
    def __init__(self, *args, **kwargs):
        departments = kwargs.pop('departments', [])
        batches = kwargs.pop('batches', [])
        subjects = kwargs.pop('subjects', [])
        super().__init__(*args, **kwargs)
        
        self.fields['department'].choices = [('', 'All Departments')] + [(d.department_id, d.department_name) for d in departments]
        self.fields['batch'].choices = [('', 'All Batches')] + [(b.batch_id, b.batch_name) for b in batches]
        self.fields['subject'].choices = [('', 'All Subjects')] + [(s.subject_id, s.subject_name) for s in subjects]
        
        # Set the min date for next_run to today
        self.fields['next_run'].widget = forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
        })
    
    class Meta:
        model = ScheduledReport
        fields = ['name', 'report_type', 'frequency', 'next_run', 'format', 'recipients', 'status']
        widgets = {
            'next_run': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'recipients': forms.TextInput(attrs={'placeholder': 'Comma-separated email addresses'})
        }
        
    def clean_recipients(self):
        """Validate email addresses"""
        recipients = self.cleaned_data['recipients']
        emails = [email.strip() for email in recipients.split(',') if email.strip()]
        
        for email in emails:
            if not email.endswith('@mbit.edu.in'):
                raise forms.ValidationError(f"Email address {email} is not valid. All emails must end with @mbit.edu.in")
        
        return recipients

class ProfileUpdateForm(forms.Form):
    """Form for updating lab assistant profile"""
    full_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    dob = forms.DateField(widget=DateInput)
    joining_year = forms.IntegerField(validators=[MinValueValidator(1980), MaxValueValidator(timezone.now().year)])
    contact_number = forms.CharField(max_length=15, required=False)

class PasswordChangeForm(forms.Form):
    """Form for changing password"""
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("New passwords do not match")
        
        return cleaned_data

class NotificationSettingsForm(forms.Form):
    """Form for updating notification settings"""
    email_leave_applications = forms.BooleanField(required=False)
    email_attendance_exceptions = forms.BooleanField(required=False)
    email_low_attendance = forms.BooleanField(required=False)
    portal_leave_applications = forms.BooleanField(required=False)
    portal_attendance_exceptions = forms.BooleanField(required=False)
    portal_low_attendance = forms.BooleanField(required=False)

class LeaveFilterForm(forms.Form):
    """Form for filtering leave applications"""
    status = forms.ChoiceField(choices=[
        ('', 'All'),
        ('pending', 'Pending'),
        ('faculty_approved', 'Faculty Approved'),
        ('lab_approved', 'Lab Approved'),
        ('rejected', 'Rejected')
    ], required=False)
    department = forms.ChoiceField(required=False)
    semester = forms.ChoiceField(choices=[
        ('', 'All'),
    ] + [(i, i) for i in range(1, 9)], required=False)
    from_date = forms.DateField(widget=DateInput, required=False)
    to_date = forms.DateField(widget=DateInput, required=False)
    
    def __init__(self, *args, **kwargs):
        departments = kwargs.pop('departments', [])
        super().__init__(*args, **kwargs)
        
        self.fields['department'].choices = [('', 'All Departments')] + [(d.department_id, d.department_name) for d in departments]

class AttendanceExceptionFilterForm(forms.Form):
    """Form for filtering attendance exceptions"""
    status = forms.ChoiceField(choices=[
        ('', 'All'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], required=False)
    department = forms.ChoiceField(required=False)
    requested_status = forms.ChoiceField(choices=[
        ('', 'All'),
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('dont_care', 'Don\'t Care')
    ], required=False)
    from_date = forms.DateField(widget=DateInput, required=False)
    to_date = forms.DateField(widget=DateInput, required=False)
    
    def __init__(self, *args, **kwargs):
        departments = kwargs.pop('departments', [])
        super().__init__(*args, **kwargs)
        
        self.fields['department'].choices = [('', 'All Departments')] + [(d.department_id, d.department_name) for d in departments]

class LowAttendanceFilterForm(forms.Form):
    """Form for filtering low attendance students"""
    department = forms.ChoiceField(required=False)
    semester = forms.ChoiceField(choices=[
        ('', 'All'),
    ] + [(i, i) for i in range(1, 9)], required=False)
    threshold = forms.IntegerField(initial=75, validators=[MinValueValidator(0), MaxValueValidator(100)])
    subject = forms.ChoiceField(required=False)
    
    def __init__(self, *args, **kwargs):
        departments = kwargs.pop('departments', [])
        subjects = kwargs.pop('subjects', [])
        super().__init__(*args, **kwargs)
        
        self.fields['department'].choices = [('', 'All Departments')] + [(d.department_id, d.department_name) for d in departments]
        self.fields['subject'].choices = [('', 'All Subjects')] + [(s.subject_id, s.subject_name) for s in subjects]

class ReportGenerationForm(forms.Form):
    """Form for generating reports"""
    report_type = forms.ChoiceField(choices=[
        ('attendance', 'Attendance Report'),
        ('leave', 'Leave Applications Report'),
        ('lab_usage', 'Lab Usage Report'),
        ('low_attendance', 'Low Attendance Report')
    ])
    department = forms.ChoiceField(required=False)
    from_date = forms.DateField(widget=DateInput, required=True)
    to_date = forms.DateField(widget=DateInput, required=True)
    format = forms.ChoiceField(choices=[
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel')
    ], initial='pdf')
    include_charts = forms.BooleanField(required=False, initial=True)
    
    def __init__(self, *args, **kwargs):
        departments = kwargs.pop('departments', [])
        super().__init__(*args, **kwargs)
        
        self.fields['department'].choices = [('', 'All Departments')] + [(d.department_id, d.department_name) for d in departments]
        
    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get('from_date')
        to_date = cleaned_data.get('to_date')
        
        if from_date and to_date and from_date > to_date:
            raise forms.ValidationError("From date cannot be after to date")
        
        return cleaned_data