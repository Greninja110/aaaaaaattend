from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from authentication.models import User, Role
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
import logging
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.urls import reverse
from django.core.paginator import Paginator
import logging
import csv
import io
import pandas as pd
import datetime
from django.core.exceptions import ValidationError
from django.shortcuts import redirect

from django.template.exceptions import TemplateDoesNotExist
from django.http import HttpResponse

from authentication.models import User, Role
from core.models import Department, AcademicYear, SystemLog
from .models import AdminSetting, BulkImportLog
from core.models import FacultySubject, ElectiveSubject, Subject, Attendance
from .forms import AcademicYearForm, DepartmentForm, AdminSettingsForm ,ElectiveSubjectForm ,SubjectForm ,StudentDetailsForm ,FacultyDetailsForm ,FacultySubjectForm

from authentication.models import User, Role
from core.models import Department, Faculty, Student, AcademicYear, SystemLog, ClassSection, Batch
from .models import AdminSetting, BulkImportLog
from .forms import (
    AcademicYearForm, DepartmentForm, AdminSettingsForm, UserCreationForm, 
    UserEditForm, UserPasswordChangeForm, BulkImportForm, FacultyDetailsForm, 
    StudentDetailsForm
)
from .utils import log_admin_action, get_current_academic_year, handle_uploaded_csv

# Then use Timetable directly without models. prefix

from authentication.models import User, Role
from core.models import Department, AcademicYear, SystemLog, ClassSection, Batch ,Timetable, FacultySubject 
from .models import AdminSetting, BulkImportLog, FacultySubject
from .forms import TimetableForm

from .utils import log_admin_action, get_current_academic_year

from django.core.paginator import Paginator

# @login_required
# def index(request):
#     """Admin Dashboard view"""
#     user = request.user
#     # Check if user has admin role
#     if user.get_role() != 'admin':
#         return render(request, 'error.html', {
#             'error_title': 'Access Denied',
#             'error_heading': 'Unauthorized Access',
#             'error_message': 'You do not have permission to access the Admin Portal.',
#             'return_url': '/'
#         })
    
#     return render(request, 'admin_portal/index.html')

logger = logging.getLogger(__name__)

def admin_required(view_func):
    """Decorator to check if the user has admin role"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.get_role() != 'admin':
            logger.warning(
                f"Unauthorized access attempt to admin portal by {request.user.email} "
                f"with role {request.user.get_role()}"
            )
            return render(request, 'error.html', {
                'error_title': 'Access Denied',
                'error_heading': 'Unauthorized Access',
                'error_message': 'You do not have permission to access the Admin Portal.',
                'return_url': '/'
            })
        
        # Log the admin action with try/except to handle missing table
        try:
            SystemLog.objects.create(
                user=request.user,
                action=f"Admin accessed {request.path}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except Exception as e:
            # Just log the error but don't prevent access
            logger.error(f"Could not log admin action: {str(e)}")
        
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
@admin_required
def index(request):
    """Admin Dashboard view"""
    # For AJAX requests, return a simple success response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    # Get the current path/URL to determine which template to use
    current_path = request.path.strip('/')
    
    try:
        # Get counts for dashboard
        user_counts = {
            'total_students': User.objects.filter(role__role_name='student').count(),
            'total_faculty': User.objects.filter(role__role_name='faculty').count(),
            'total_departments': Department.objects.count(),
            'active_users': User.objects.filter(is_active=True).count()
        }
        
        # Get recent system logs
        try:
            recent_logs = SystemLog.objects.select_related('user').order_by('-created_at')[:10]
        except:
            recent_logs = []
        
        # Get role distribution for pie chart
        role_distribution = list(User.objects.values('role__role_name')
                             .annotate(count=Count('user_id'))
                             .order_by('role__role_name'))
        
        # Get current academic year
        current_academic_year = None
        try:
            current_academic_year = AcademicYear.objects.get(is_current=True)
        except (AcademicYear.DoesNotExist, Exception):
            pass
            
        context = {
            'user_counts': user_counts,
            'recent_logs': recent_logs,
            'role_distribution': role_distribution,
            'current_academic_year': current_academic_year,
            'active_page': 'dashboard'  # Add this line to set active page
        }
        
        # Check if this is the dashboard URL or the root URL
        if 'dashboard' in current_path:
            # Use the detailed dashboard template
            return render(request, 'admin_portal/dashboard/index.html', context)
        else:
            # Fixed indentation here
            return redirect('admin_portal:dashboard')
            
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}", exc_info=True)
        messages.error(request, f"An error occurred while loading the dashboard: {str(e)}")
        return render(request, 'admin_portal/index.html', {'error': str(e)})
    

@login_required
@admin_required
def user_list(request):
    """View for listing all users with filtering and pagination"""
    # Get query parameters
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    page_number = request.GET.get('page', 1)
    
    # Base queryset
    users = User.objects.select_related('role').order_by('full_name')
    
    # Apply filters
    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query) | 
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    if role_filter:
        users = users.filter(role__role_name=role_filter)
        
    if status_filter:
        is_active = status_filter == 'active'
        users = users.filter(is_active=is_active)
    
    # Pagination
    paginator = Paginator(users, 20)  # 20 users per page
    page_obj = paginator.get_page(page_number)
    
    # Get all roles for filter dropdown
    roles = Role.objects.all()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'roles': roles,
        'active_page': 'users'
    }
    
    return render(request, 'admin_portal/users/list.html', context)

@login_required
@admin_required
def user_create(request):
    """View for creating a new user"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    
                    # Create additional details based on role
                    role_name = user.role.role_name
                    
                    # Log the action
                    log_admin_action(
                        request.user,
                        f"Created new user: {user.email} with role {role_name}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"User {user.full_name} created successfully.")
                    
                    # If role requires additional details, redirect to appropriate form
                    if role_name in ['faculty', 'student', 'lab_assistant']:
                        return redirect('admin_portal:user_additional_details', user_id=user.user_id, role=role_name)
                    
                    return redirect('admin_portal:user_list')
            except Exception as e:
                logger.error(f"Error creating user: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating user: {str(e)}")
    else:
        form = UserCreationForm()
    
    return render(request, 'admin_portal/users/create.html', {
        'form': form,
        'active_page': 'users'
    })

@login_required
@admin_required
def user_edit(request, user_id):
    """View for editing an existing user"""
    user = get_object_or_404(User, user_id=user_id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Save changes
                    old_role = user.role.role_name
                    user = form.save()
                    new_role = user.role.role_name
                    
                    # Log the action
                    log_admin_action(
                        request.user,
                        f"Updated user: {user.email}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"User {user.full_name} updated successfully.")
                    
                    # If role changed to one that requires additional details and they don't have them yet
                    if old_role != new_role and new_role in ['faculty', 'student', 'lab_assistant']:
                        # Check if they already have details
                        if new_role == 'faculty' and not hasattr(user, 'faculty'):
                            return redirect('admin_portal:user_additional_details', user_id=user.user_id, role=new_role)
                        elif new_role == 'student' and not hasattr(user, 'student'):
                            return redirect('admin_portal:user_additional_details', user_id=user.user_id, role=new_role)
                    
                    return redirect('admin_portal:user_list')
            except Exception as e:
                logger.error(f"Error updating user: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating user: {str(e)}")
    else:
        form = UserEditForm(instance=user)
    
    # Check if user has associated details
    has_additional_details = False
    role_name = user.role.role_name
    
    if role_name == 'faculty' and hasattr(user, 'faculty'):
        has_additional_details = True
    elif role_name == 'student' and hasattr(user, 'student'):
        has_additional_details = True
    
    return render(request, 'admin_portal/users/edit.html', {
        'form': form,
        'user_obj': user,
        'has_additional_details': has_additional_details,
        'role_name': role_name,
        'active_page': 'users'
    })

@login_required
@admin_required
def user_delete(request, user_id):
    """View for deleting a user"""
    user = get_object_or_404(User, user_id=user_id)
    
    if request.method == 'POST':
        try:
            # Store info for logging
            email = user.email
            full_name = user.full_name
            role = user.role.role_name
            
            # Delete user
            user.delete()
            
            # Log the action
            log_admin_action(
                request.user,
                f"Deleted user: {email} ({role})",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"User {full_name} deleted successfully.")
            return redirect('admin_portal:user_list')
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}", exc_info=True)
            messages.error(request, f"Error deleting user: {str(e)}")
            return redirect('admin_portal:user_edit', user_id=user_id)
    
    return render(request, 'admin_portal/users/delete_confirm.html', {
        'user_obj': user,
        'active_page': 'users'
    })

@login_required
@admin_required
def user_additional_details(request, user_id, role):
    """View for adding additional details for faculty/student/lab_assistant"""
    user = get_object_or_404(User, user_id=user_id)
    
    # If role doesn't match user's current role, redirect
    if user.role.role_name != role:
        messages.error(request, f"User does not have {role} role.")
        return redirect('admin_portal:user_edit', user_id=user_id)
    
    if role == 'faculty':
        return faculty_details(request, user)
    elif role == 'student':
        return student_details(request, user)
    else:
        messages.error(request, f"Adding details for {role} role is not implemented yet.")
        return redirect('admin_portal:user_edit', user_id=user_id)

def faculty_details(request, user):
    """Helper function to handle faculty details form"""
    # Check if faculty already exists
    try:
        faculty = Faculty.objects.get(user=user)
        form = FacultyDetailsForm(initial={
            'employee_id': faculty.employee_id,
            'department': faculty.department,
            'designation': faculty.designation,
            'joining_year': faculty.joining_year,
            'dob': faculty.dob
        })
        is_update = True
    except Faculty.DoesNotExist:
        form = FacultyDetailsForm()
        is_update = False
    
    if request.method == 'POST':
        form = FacultyDetailsForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Check if employee_id is already in use
                    employee_id = form.cleaned_data['employee_id']
                    if Faculty.objects.filter(employee_id=employee_id).exclude(user=user).exists():
                        form.add_error('employee_id', 'This employee ID is already in use.')
                        raise ValidationError("Employee ID already in use")
                    
                    faculty_data = {
                        'user': user,
                        'employee_id': employee_id,
                        'department': form.cleaned_data['department'],
                        'designation': form.cleaned_data['designation'],
                        'joining_year': form.cleaned_data['joining_year'],
                        'dob': form.cleaned_data['dob'],
                        'status': 'active'
                    }
                    
                    if is_update:
                        Faculty.objects.filter(user=user).update(**faculty_data)
                        faculty = Faculty.objects.get(user=user)
                        action = "Updated"
                    else:
                        faculty = Faculty.objects.create(**faculty_data)
                        action = "Added"
                    
                    # Log the action
                    log_admin_action(
                        request.user,
                        f"{action} faculty details for {user.email}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Faculty details for {user.full_name} saved successfully.")
                    return redirect('admin_portal:user_list')
            except ValidationError:
                # Form will display the error
                pass
            except Exception as e:
                logger.error(f"Error saving faculty details: {str(e)}", exc_info=True)
                messages.error(request, f"Error saving faculty details: {str(e)}")
    
    return render(request, 'admin_portal/users/faculty_details.html', {
        'form': form,
        'user_obj': user,
        'is_update': is_update,
        'active_page': 'users'
    })

def student_details(request, user):
    """Helper function to handle student details form"""
    # Check if student already exists
    try:
        student = Student.objects.get(user=user)
        form = StudentDetailsForm(initial={
            'roll_number': student.roll_number,
            'admission_year': student.admission_year,
            'department': student.department,
            'current_semester': student.current_semester,
            'class_section': student.class_section,
            'dob': student.dob
        })
        is_update = True
    except Student.DoesNotExist:
        form = StudentDetailsForm()
        is_update = False
    
    if request.method == 'POST':
        form = StudentDetailsForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Check if roll_number is already in use
                    roll_number = form.cleaned_data['roll_number']
                    if Student.objects.filter(roll_number=roll_number).exclude(user=user).exists():
                        form.add_error('roll_number', 'This roll number is already in use.')
                        raise ValidationError("Roll number already in use")
                    
                    # Get a default batch if needed
                    default_batch = Batch.objects.first()
                    
                    student_data = {
                        'user': user,
                        'roll_number': roll_number,
                        'admission_year': form.cleaned_data['admission_year'],
                        'department': form.cleaned_data['department'],
                        'current_semester': form.cleaned_data['current_semester'],
                        'class_section': form.cleaned_data['class_section'],
                        'dob': form.cleaned_data['dob'],
                        'batch': default_batch,
                        'status': 'active'
                    }
                    
                    if is_update:
                        # Update rather than create to preserve relationships
                        Student.objects.filter(user=user).update(**student_data)
                        student = Student.objects.get(user=user)
                        action = "Updated"
                    else:
                        student = Student.objects.create(**student_data)
                        action = "Added"
                    
                    # Log the action
                    log_admin_action(
                        request.user,
                        f"{action} student details for {user.email}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Student details for {user.full_name} saved successfully.")
                    return redirect('admin_portal:user_list')
            except ValidationError:
                # Form will display the error
                pass
            except Exception as e:
                logger.error(f"Error saving student details: {str(e)}", exc_info=True)
                messages.error(request, f"Error saving student details: {str(e)}")
    
    return render(request, 'admin_portal/users/student_details.html', {
        'form': form,
        'user_obj': user,
        'is_update': is_update,
        'active_page': 'users'
    })

@login_required
@admin_required
def change_password(request, user_id):
    """View for changing a user's password"""
    user = get_object_or_404(User, user_id=user_id)
    
    if request.method == 'POST':
        form = UserPasswordChangeForm(request.POST)
        if form.is_valid():
            try:
                # Set new password
                user.set_password(form.cleaned_data['password1'])
                user.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Changed password for user: {user.email}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Password for {user.full_name} changed successfully.")
                return redirect('admin_portal:user_edit', user_id=user_id)
            except Exception as e:
                logger.error(f"Error changing password: {str(e)}", exc_info=True)
                messages.error(request, f"Error changing password: {str(e)}")
    else:
        form = UserPasswordChangeForm()
    
    return render(request, 'admin_portal/users/change_password.html', {
        'form': form,
        'user_obj': user,
        'active_page': 'users'
    })

@login_required
@admin_required
def bulk_import_users(request):
    """View for bulk importing users from CSV/Excel"""
    if request.method == 'POST':
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Process the uploaded file
                file = request.FILES['file']
                import_type = form.cleaned_data['import_type']
                
                # Use utility function to handle CSV
                result = handle_uploaded_csv(file, import_type, request.user)
                
                if result['success']:
                    messages.success(
                        request, 
                        f"Successfully imported {result['records_processed']} {import_type}. "
                        f"Failed: {result['records_failed']}."
                    )
                    return redirect('admin_portal:import_results', log_id=result.get('log_id'))
                else:
                    messages.error(request, f"Import failed: {result['error']}")
            except Exception as e:
                logger.error(f"Error in bulk import: {str(e)}", exc_info=True)
                messages.error(request, f"Error processing import: {str(e)}")
    else:
        form = BulkImportForm()
    
    # Get recent import logs for display
    recent_imports = BulkImportLog.objects.select_related('user').order_by('-created_at')[:5]
    
    return render(request, 'admin_portal/users/bulk_import.html', {
        'form': form,
        'recent_imports': recent_imports,
        'active_page': 'import'
    })

@login_required
@admin_required
def import_results(request, log_id):
    """View for displaying results of a bulk import operation"""
    import_log = get_object_or_404(BulkImportLog, import_id=log_id)
    
    return render(request, 'admin_portal/users/import_results.html', {
        'import_log': import_log,
        'active_page': 'import'
    })

@login_required
@admin_required
def download_import_template(request, import_type):
    """View for downloading import templates"""
    if import_type not in ['students', 'faculty', 'lab_assistant']:
        messages.error(request, f"Invalid template type: {import_type}")
        return redirect('admin_portal:bulk_import_users')
    
    # Create a response with proper content-type
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{import_type}_import_template.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write appropriate headers based on import type
    if import_type == 'students':
        writer.writerow([
            'email', 'full_name', 'username', 'roll_number', 'admission_year', 
            'department_code', 'current_semester', 'section', 'dob'
        ])
        # Add sample data
        writer.writerow([
            'student1@mbit.edu.in', 'John Doe', 'john.doe', '2025CE001', '2025',
            'CE', '1', 'A', '2000-01-01'
        ])
    elif import_type == 'faculty':
        writer.writerow([
            'email', 'full_name', 'username', 'employee_id', 
            'department_code', 'designation', 'joining_year', 'dob'
        ])
        # Add sample data
        writer.writerow([
            'faculty1@mbit.edu.in', 'Jane Smith', 'jane.smith', 'FAC001',
            'CE', 'Assistant Professor', '2020', '1980-01-01'
        ])
    else:  # lab_assistant
        writer.writerow([
            'email', 'full_name', 'username', 'employee_id', 
            'department_code', 'joining_year', 'dob'
        ])
        # Add sample data
        writer.writerow([
            'lab1@mbit.edu.in', 'Alex Johnson', 'alex.johnson', 'LAB001',
            'CE', '2022', '1990-01-01'
        ])
    
    return response

@login_required
@admin_required
def department_list(request):
    """View for listing all departments"""
    departments = Department.objects.all().order_by('department_name')
    
    context = {
        'departments': departments,
        'active_page': 'departments'
    }
    
    return render(request, 'admin_portal/departments/list.html', context)

@login_required
@admin_required
def department_create(request):
    """View for creating a new department"""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            try:
                department = form.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Created new department: {department.department_name} ({department.department_code})",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Department {department.department_name} created successfully.")
                return redirect('admin_portal:department_list')
            except Exception as e:
                logger.error(f"Error creating department: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating department: {str(e)}")
    else:
        form = DepartmentForm()
    
    return render(request, 'admin_portal/departments/create.html', {
        'form': form,
        'active_page': 'departments'
    })

@login_required
@admin_required
def department_edit(request, department_id):
    """View for editing a department"""
    department = get_object_or_404(Department, department_id=department_id)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            try:
                department = form.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Updated department: {department.department_name} ({department.department_code})",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Department {department.department_name} updated successfully.")
                return redirect('admin_portal:department_list')
            except Exception as e:
                logger.error(f"Error updating department: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating department: {str(e)}")
    else:
        form = DepartmentForm(instance=department)
    
    return render(request, 'admin_portal/departments/edit.html', {
        'form': form,
        'department': department,
        'active_page': 'departments'
    })

@login_required
@admin_required
def department_delete(request, department_id):
    """View for deleting a department"""
    department = get_object_or_404(Department, department_id=department_id)
    
    if request.method == 'POST':
        try:
            # Store info for logging
            name = department.department_name
            code = department.department_code
            
            # Attempt to delete
            department.delete()
            
            # Log the action
            log_admin_action(
                request.user,
                f"Deleted department: {name} ({code})",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"Department {name} deleted successfully.")
            return redirect('admin_portal:department_list')
        except Exception as e:
            logger.error(f"Error deleting department: {str(e)}", exc_info=True)
            messages.error(request, f"Error deleting department: {str(e)}. It might be in use by other records.")
            return redirect('admin_portal:department_edit', department_id=department_id)
    
    return render(request, 'admin_portal/departments/delete_confirm.html', {
        'department': department,
        'active_page': 'departments'
    })

@login_required
@admin_required
def academic_year_list(request):
    """View for listing all academic years"""
    academic_years = AcademicYear.objects.all().order_by('-year_start')
    
    context = {
        'academic_years': academic_years,
        'active_page': 'academic'
    }
    
    return render(request, 'admin_portal/academic/year_list.html', context)

@login_required
@admin_required
def academic_year_create(request):
    """View for creating a new academic year"""
    if request.method == 'POST':
        form = AcademicYearForm(request.POST)
        if form.is_valid():
            try:
                academic_year = form.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Created new academic year: {academic_year.year_start}-{academic_year.year_end}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Academic year {academic_year.year_start}-{academic_year.year_end} created successfully.")
                return redirect('admin_portal:academic_year_list')
            except Exception as e:
                logger.error(f"Error creating academic year: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating academic year: {str(e)}")
    else:
        # Get current year for default value
        current_year = timezone.now().year
        form = AcademicYearForm(initial={'year_start': current_year})
    
    return render(request, 'admin_portal/academic/year_create.html', {
        'form': form,
        'active_page': 'academic'
    })

@login_required
@admin_required
def academic_year_edit(request, year_id):
    """View for editing an academic year"""
    academic_year = get_object_or_404(AcademicYear, academic_year_id=year_id)
    
    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=academic_year)
        if form.is_valid():
            try:
                academic_year = form.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Updated academic year: {academic_year.year_start}-{academic_year.year_end}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Academic year {academic_year.year_start}-{academic_year.year_end} updated successfully.")
                return redirect('admin_portal:academic_year_list')
            except Exception as e:
                logger.error(f"Error updating academic year: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating academic year: {str(e)}")
    else:
        form = AcademicYearForm(instance=academic_year)
    
    return render(request, 'admin_portal/academic/year_edit.html', {
        'form': form,
        'academic_year': academic_year,
        'active_page': 'academic'
    })

@login_required
@admin_required
def academic_year_delete(request, year_id):
    """View for deleting an academic year"""
    academic_year = get_object_or_404(AcademicYear, academic_year_id=year_id)
    
    if request.method == 'POST':
        try:
            # Store info for logging
            year_start = academic_year.year_start
            year_end = academic_year.year_end
            
            # Attempt to delete
            academic_year.delete()
            
            # Log the action
            log_admin_action(
                request.user,
                f"Deleted academic year: {year_start}-{year_end}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"Academic year {year_start}-{year_end} deleted successfully.")
            return redirect('admin_portal:academic_year_list')
        except Exception as e:
            logger.error(f"Error deleting academic year: {str(e)}", exc_info=True)
            messages.error(request, f"Error deleting academic year: {str(e)}. It might be in use by other records.")
            return redirect('admin_portal:academic_year_edit', year_id=year_id)
    
    return render(request, 'admin_portal/academic/year_delete_confirm.html', {
        'academic_year': academic_year,
        'active_page': 'academic'
    })

@login_required
@admin_required
def set_current_academic_year(request, year_id):
    """View for setting the current academic year"""
    academic_year = get_object_or_404(AcademicYear, academic_year_id=year_id)
    
    try:
        # Set is_current=False for all academic years
        AcademicYear.objects.update(is_current=False)
        
        # Set is_current=True for the selected academic year
        academic_year.is_current = True
        academic_year.save()
        
        # Log the action
        log_admin_action(
            request.user,
            f"Set current academic year to: {academic_year.year_start}-{academic_year.year_end}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(request, f"Current academic year set to {academic_year.year_start}-{academic_year.year_end}.")
    except Exception as e:
        logger.error(f"Error setting current academic year: {str(e)}", exc_info=True)
        messages.error(request, f"Error setting current academic year: {str(e)}")
    
    return redirect('admin_portal:academic_year_list')


@login_required
@admin_required
def subject_list(request):
    """View for listing all subjects"""
    # Get query parameters
    search_query = request.GET.get('search', '')
    department_filter = request.GET.get('department', '')
    semester_filter = request.GET.get('semester', '')
    type_filter = request.GET.get('type', '')
    
    # Base queryset
    subjects = Subject.objects.select_related('department').order_by('subject_code')
    
    # Apply filters
    if search_query:
        subjects = subjects.filter(
            Q(subject_name__icontains=search_query) | 
            Q(subject_code__icontains=search_query)
        )
    
    if department_filter:
        subjects = subjects.filter(department__department_id=department_filter)
        
    if semester_filter:
        subjects = subjects.filter(semester=semester_filter)
        
    if type_filter:
        if type_filter == 'theory':
            subjects = subjects.filter(has_theory=True)
        elif type_filter == 'lab':
            subjects = subjects.filter(has_lab=True)
        elif type_filter == 'elective':
            subjects = subjects.filter(is_elective=True)
    
    # Get all departments for filter dropdown
    departments = Department.objects.all()
    
    context = {
        'subjects': subjects,
        'search_query': search_query,
        'department_filter': department_filter,
        'semester_filter': semester_filter,
        'type_filter': type_filter,
        'departments': departments,
        'semesters': range(1, 9),  # 1 to 8
        'active_page': 'subjects'
    }
    
    return render(request, 'admin_portal/subjects/list.html', context)

@login_required
@admin_required
def subject_create(request):
    """View for creating a new subject"""
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    subject = form.save()
                    
                    # If it's an elective, handle elective details
                    if subject.is_elective:
                        elective_form = ElectiveSubjectForm(request.POST)
                        if elective_form.is_valid():
                            elective = elective_form.save(commit=False)
                            elective.subject = subject
                            elective.save()
                        else:
                            # If elective form is invalid, raise validation error
                            for error in elective_form.errors.values():
                                raise ValidationError(error)
                    
                    # Log the action
                    log_admin_action(
                        request.user,
                        f"Created new subject: {subject.subject_name} ({subject.subject_code})",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Subject {subject.subject_name} created successfully.")
                    return redirect('admin_portal:subject_list')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error creating subject: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating subject: {str(e)}")
    else:
        form = SubjectForm()
        
    # Show elective form only if is_elective is checked
    elective_form = ElectiveSubjectForm()
    
    return render(request, 'admin_portal/subjects/create.html', {
        'form': form,
        'elective_form': elective_form,
        'active_page': 'subjects'
    })

@login_required
@admin_required
def subject_edit(request, subject_id):
    """View for editing a subject"""
    subject = get_object_or_404(Subject, subject_id=subject_id)
    
    # Check if subject has an elective record
    try:
        elective = ElectiveSubject.objects.get(subject=subject)
        has_elective = True
    except ElectiveSubject.DoesNotExist:
        elective = None
        has_elective = False
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            try:
                with transaction.atomic():
                    subject = form.save()
                    
                    # Handle elective details
                    if subject.is_elective:
                        if has_elective:
                            # Update existing elective
                            elective_form = ElectiveSubjectForm(request.POST, instance=elective)
                        else:
                            # Create new elective
                            elective_form = ElectiveSubjectForm(request.POST)
                            
                        if elective_form.is_valid():
                            elective = elective_form.save(commit=False)
                            elective.subject = subject
                            elective.save()
                        else:
                            # If elective form is invalid, raise validation error
                            for error in elective_form.errors.values():
                                raise ValidationError(error)
                    elif has_elective:
                        # Subject is no longer an elective, delete elective record
                        elective.delete()
                    
                    # Log the action
                    log_admin_action(
                        request.user,
                        f"Updated subject: {subject.subject_name} ({subject.subject_code})",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Subject {subject.subject_name} updated successfully.")
                    return redirect('admin_portal:subject_list')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error updating subject: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating subject: {str(e)}")
    else:
        form = SubjectForm(instance=subject)
        
    # Initialize elective form if needed
    if has_elective:
        elective_form = ElectiveSubjectForm(instance=elective)
    else:
        elective_form = ElectiveSubjectForm()
    
    return render(request, 'admin_portal/subjects/edit.html', {
        'form': form,
        'elective_form': elective_form,
        'subject': subject,
        'has_elective': has_elective,
        'active_page': 'subjects'
    })

@login_required
@admin_required
def subject_delete(request, subject_id):
    """View for deleting a subject"""
    subject = get_object_or_404(Subject, subject_id=subject_id)
    
    if request.method == 'POST':
        try:
            # Store info for logging
            name = subject.subject_name
            code = subject.subject_code
            
            # Attempt to delete
            subject.delete()
            
            # Log the action
            log_admin_action(
                request.user,
                f"Deleted subject: {name} ({code})",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"Subject {name} deleted successfully.")
            return redirect('admin_portal:subject_list')
        except Exception as e:
            logger.error(f"Error deleting subject: {str(e)}", exc_info=True)
            messages.error(request, f"Error deleting subject: {str(e)}. It might be in use by other records.")
            return redirect('admin_portal:subject_edit', subject_id=subject_id)
    
    return render(request, 'admin_portal/subjects/delete_confirm.html', {
        'subject': subject,
        'active_page': 'subjects'
    })

@login_required
@admin_required
def faculty_assignment_list(request):
    """View for listing all faculty assignments"""
    # Get query parameters
    faculty_filter = request.GET.get('faculty', '')
    subject_filter = request.GET.get('subject', '')
    department_filter = request.GET.get('department', '')
    year_filter = request.GET.get('academic_year', '')
    
    # Base queryset
    assignments = FacultySubject.objects.select_related(
        'faculty', 'faculty__user', 'subject', 'class_section', 'batch', 'academic_year'
    ).order_by('faculty__user__full_name', 'subject__subject_code')
    
    # Apply filters
    if faculty_filter:
        assignments = assignments.filter(faculty__faculty_id=faculty_filter)
        
    if subject_filter:
        assignments = assignments.filter(subject__subject_id=subject_filter)
        
    if department_filter:
        assignments = assignments.filter(subject__department__department_id=department_filter)
        
    if year_filter:
        assignments = assignments.filter(academic_year__academic_year_id=year_filter)
    else:
        # Default to current academic year if no filter specified
        try:
            current_year = AcademicYear.objects.get(is_current=True)
            assignments = assignments.filter(academic_year=current_year)
            year_filter = current_year.academic_year_id
        except AcademicYear.DoesNotExist:
            pass
    
    # Get filter options
    faculties = Faculty.objects.select_related('user').order_by('user__full_name')
    subjects = Subject.objects.order_by('subject_name')
    departments = Department.objects.order_by('department_name')
    academic_years = AcademicYear.objects.order_by('-year_start')
    
    context = {
        'assignments': assignments,
        'faculties': faculties,
        'subjects': subjects,
        'departments': departments,
        'academic_years': academic_years,
        'faculty_filter': faculty_filter,
        'subject_filter': subject_filter,
        'department_filter': department_filter,
        'year_filter': year_filter,
        'active_page': 'faculty'
    }
    
    return render(request, 'admin_portal/faculty_assignment/list.html', context)

@login_required
@admin_required
def faculty_assignment_create(request):
    """View for creating a new faculty assignment"""
    if request.method == 'POST':
        form = FacultySubjectForm(request.POST)
        if form.is_valid():
            try:
                assignment = form.save()
                
                # Log the action
                faculty_name = assignment.faculty.user.full_name
                subject_name = assignment.subject.subject_name
                log_admin_action(
                    request.user,
                    f"Assigned faculty {faculty_name} to subject {subject_name}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Faculty assignment created successfully.")
                return redirect('admin_portal:faculty_assignment_list')
            except Exception as e:
                logger.error(f"Error creating faculty assignment: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating faculty assignment: {str(e)}")
    else:
        form = FacultySubjectForm()
    
    return render(request, 'admin_portal/faculty_assignment/create.html', {
        'form': form,
        'active_page': 'faculty_assignment'
    })

@login_required
@admin_required
def faculty_assignment_edit(request, assignment_id):
    """View for editing a faculty assignment"""
    assignment = get_object_or_404(FacultySubject, faculty_subject_id=assignment_id)
    
    if request.method == 'POST':
        form = FacultySubjectForm(request.POST, instance=assignment)
        if form.is_valid():
            try:
                assignment = form.save()
                
                # Log the action
                faculty_name = assignment.faculty.user.full_name
                subject_name = assignment.subject.subject_name
                log_admin_action(
                    request.user,
                    f"Updated faculty assignment: {faculty_name} - {subject_name}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Faculty assignment updated successfully.")
                return redirect('admin_portal:faculty_assignment_list')
            except Exception as e:
                logger.error(f"Error updating faculty assignment: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating faculty assignment: {str(e)}")
    else:
        form = FacultySubjectForm(instance=assignment)
    
    return render(request, 'admin_portal/faculty_assignment/edit.html', {
        'form': form,
        'assignment': assignment,
        'active_page': 'faculty_assignment'
    })

@login_required
@admin_required
def faculty_assignment_delete(request, assignment_id):
    """View for deleting a faculty assignment"""
    assignment = get_object_or_404(FacultySubject, faculty_subject_id=assignment_id)
    
    if request.method == 'POST':
        try:
            # Store info for logging
            faculty_name = assignment.faculty.user.full_name
            subject_name = assignment.subject.subject_name
            
            # Attempt to delete
            assignment.delete()
            
            # Log the action
            log_admin_action(
                request.user,
                f"Deleted faculty assignment: {faculty_name} - {subject_name}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f"Faculty assignment deleted successfully.")
            return redirect('admin_portal:faculty_assignment_list')
        except Exception as e:
            logger.error(f"Error deleting faculty assignment: {str(e)}", exc_info=True)
            messages.error(request, f"Error deleting faculty assignment: {str(e)}. It might be in use by other records.")
            return redirect('admin_portal:faculty_assignment_edit', assignment_id=assignment_id)
    
    return render(request, 'admin_portal/faculty_assignment/delete_confirm.html', {
        'assignment': assignment,
        'active_page': 'faculty_assignment'
    })

@login_required
@admin_required
def get_subjects_by_department(request):
    """AJAX view to get subjects filtered by department"""
    department_id = request.GET.get('department_id')
    
    if department_id:
        subjects = Subject.objects.filter(department__department_id=department_id).values('subject_id', 'subject_name')
        return JsonResponse(list(subjects), safe=False)
    
    return JsonResponse([], safe=False)

@login_required
@admin_required
def get_class_sections_by_department(request):
    """AJAX view to get class sections filtered by department"""
    department_id = request.GET.get('department_id')
    
    if department_id:
        sections = ClassSection.objects.filter(department__department_id=department_id).values('class_section_id', 'section_name')
        return JsonResponse(list(sections), safe=False)
    
    return JsonResponse([], safe=False)


@login_required
@admin_required
def report_dashboard(request):
    """View for the reports dashboard"""
    context = {
        'active_page': 'reports'
    }
    
    return render(request, 'admin_portal/reports/dashboard.html', context)

@login_required
@admin_required
def attendance_report(request):
    """View for generating attendance reports"""
    # Get query parameters
    department_filter = request.GET.get('department', '')
    semester_filter = request.GET.get('semester', '')
    subject_filter = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Initialize report data
    report_data = None
    export_csv = request.GET.get('export', '') == 'csv'
    
    # Handle report generation
    if department_filter or semester_filter or subject_filter:
        # Example query - in a real implementation, this would be more complex
        # and fetch actual attendance data from your attendance table
        report_data = {
            'title': 'Attendance Report',
            'parameters': {
                'Department': department_filter,
                'Semester': semester_filter,
                'Subject': subject_filter,
                'Date Range': f"{date_from} to {date_to}" if date_from and date_to else "All dates"
            },
            'summary': {
                'Total Students': 120,
                'Average Attendance': '82.5%',
                'Students Below Threshold': 15
            },
            'data': []  # This would contain the actual data
        }
        
        # If export requested, generate CSV
        if export_csv:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Roll Number', 'Student Name', 'Total Classes', 'Present', 'Absent', 'Percentage'])
            
            # Example data - replace with actual data in real implementation
            writer.writerow(['CE2001', 'John Doe', 25, 22, 3, '88.0%'])
            writer.writerow(['CE2002', 'Jane Smith', 25, 20, 5, '80.0%'])
            
            return response
    
    # Get filter options
    departments = Department.objects.order_by('department_name')
    subjects = Subject.objects.order_by('subject_name')
    
    context = {
        'departments': departments,
        'subjects': subjects,
        'department_filter': department_filter,
        'semester_filter': semester_filter,
        'subject_filter': subject_filter,
        'date_from': date_from,
        'date_to': date_to,
        'report_data': report_data,
        'active_page': 'reports'
    }
    
    return render(request, 'admin_portal/reports/attendance.html', context)

@login_required
@admin_required
def faculty_workload_report(request):
    """View for generating faculty workload reports"""
    # Get query parameters
    department_filter = request.GET.get('department', '')
    faculty_filter = request.GET.get('faculty', '')
    academic_year_filter = request.GET.get('academic_year', '')
    
    # Initialize report data
    report_data = None
    export_csv = request.GET.get('export', '') == 'csv'
    
    # Handle report generation
    if department_filter or faculty_filter:
        # Example query - adjust with your actual data model
        report_data = {
            'title': 'Faculty Workload Report',
            'parameters': {
                'Department': department_filter,
                'Faculty': faculty_filter,
                'Academic Year': academic_year_filter
            },
            'summary': {
                'Total Faculty': 10,
                'Average Weekly Hours': 32.5,
                'Overloaded Faculty': 2
            },
            'data': []  # This would contain the actual data
        }
        
        # If export requested, generate CSV
        if export_csv:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="faculty_workload_report.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Faculty ID', 'Name', 'Department', 'Weekly Hours', 'Subjects Count', 'Status'])
            
            # Example data - replace with actual data in real implementation
            writer.writerow(['FAC001', 'Dr. John Smith', 'Computer Engineering', 38, 4, 'Normal'])
            writer.writerow(['FAC002', 'Dr. Jane Doe', 'Information Technology', 42, 5, 'Overloaded'])
            
            return response
    
    # Get filter options
    departments = Department.objects.order_by('department_name')
    faculties = Faculty.objects.select_related('user').order_by('user__full_name')
    academic_years = AcademicYear.objects.order_by('-year_start')
    
    context = {
        'departments': departments,
        'faculties': faculties,
        'academic_years': academic_years,
        'department_filter': department_filter,
        'faculty_filter': faculty_filter,
        'academic_year_filter': academic_year_filter,
        'report_data': report_data,
        'active_page': 'reports'
    }
    
    return render(request, 'admin_portal/reports/faculty_workload.html', context)

@login_required
@admin_required
def settings_page(request):
    """View for system settings"""
    if request.method == 'POST':
        form = AdminSettingsForm(request.POST)
        if form.is_valid():
            try:
                # Save settings to database
                settings = form.cleaned_data
                
                # In a real implementation, you'd save these to your AdminSetting model
                for key, value in settings.items():
                    AdminSetting.objects.update_or_create(
                        setting_key=key,
                        defaults={
                            'setting_value': str(value),
                            'updated_by': request.user
                        }
                    )
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Updated system settings",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, "Settings updated successfully.")
            except Exception as e:
                logger.error(f"Error updating settings: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating settings: {str(e)}")
    else:
        # Initialize form with current settings
        initial_settings = {}
        
        # Get settings from database
        settings = AdminSetting.objects.filter(setting_key__in=[
            'attendance_threshold', 'default_password', 'session_timeout', 'enable_email_notifications'
        ])
        
        # Convert to dictionary for form initial values
        for setting in settings:
            if setting.setting_key == 'enable_email_notifications':
                initial_settings[setting.setting_key] = setting.setting_value.lower() == 'true'
            elif setting.setting_key in ['attendance_threshold', 'session_timeout']:
                initial_settings[setting.setting_key] = int(setting.setting_value)
            else:
                initial_settings[setting.setting_key] = setting.setting_value
        
        # Set defaults for missing settings
        if 'attendance_threshold' not in initial_settings:
            initial_settings['attendance_threshold'] = 75
        if 'default_password' not in initial_settings:
            initial_settings['default_password'] = '123'
        if 'session_timeout' not in initial_settings:
            initial_settings['session_timeout'] = 30
        if 'enable_email_notifications' not in initial_settings:
            initial_settings['enable_email_notifications'] = True
        
        form = AdminSettingsForm(initial=initial_settings)
    
    return render(request, 'admin_portal/settings/index.html', {
        'form': form,
        'active_page': 'settings'
    })

@login_required
@admin_required
def timetable_view(request):
    """View for listing and filtering timetable entries"""
    # Get query parameters
    faculty_filter = request.GET.get('faculty', '')
    department_filter = request.GET.get('department', '')
    day_filter = request.GET.get('day', '')
    class_section_filter = request.GET.get('class_section', '')
    
    # Get default academic year
    try:
        academic_year = AcademicYear.objects.get(is_current=True)
        academic_year_id = academic_year.academic_year_id
    except AcademicYear.DoesNotExist:
        academic_year = None
        academic_year_id = None
    
    # Override with query parameter if provided
    academic_year_filter = request.GET.get('academic_year', str(academic_year_id) if academic_year_id else '')
    
    # Base queryset
    timetable_entries = None
    try:
        timetable_entries = Timetable.objects.select_related(
            'faculty_subject', 
            'faculty_subject__faculty', 
            'faculty_subject__faculty__user', 
            'faculty_subject__subject',
            'faculty_subject__class_section',
            'faculty_subject__batch',
            'academic_year'
        ).order_by('day_of_week', 'start_time')
        
        # Apply filters
        if academic_year_filter:
            timetable_entries = timetable_entries.filter(academic_year_id=academic_year_filter)
            
        if faculty_filter:
            timetable_entries = timetable_entries.filter(faculty_subject__faculty_id=faculty_filter)
            
        if department_filter:
            timetable_entries = timetable_entries.filter(
                faculty_subject__subject__department_id=department_filter
            )
            
        if day_filter:
            timetable_entries = timetable_entries.filter(day_of_week=day_filter)
            
        if class_section_filter:
            timetable_entries = timetable_entries.filter(
                faculty_subject__class_section_id=class_section_filter
            )
    except Exception as e:
        logger.error(f"Error fetching timetable entries: {str(e)}", exc_info=True)
        messages.error(request, f"Error loading timetable data: {str(e)}")
        timetable_entries = []
    
    # Get filter options
    departments = Department.objects.order_by('department_name')
    faculties = Faculty.objects.select_related('user').order_by('user__full_name')
    class_sections = ClassSection.objects.select_related('department').order_by('section_name')
    academic_years = AcademicYear.objects.order_by('-year_start')
    
    # Day of week choices
    day_choices = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday')
    ]
    
    context = {
        'timetable_entries': timetable_entries,
        'departments': departments,
        'faculties': faculties,
        'class_sections': class_sections,
        'academic_years': academic_years,
        'day_choices': day_choices,
        'faculty_filter': faculty_filter,
        'department_filter': department_filter,
        'day_filter': day_filter,
        'class_section_filter': class_section_filter,
        'academic_year_filter': academic_year_filter,
        'current_academic_year': academic_year,
        'active_page': 'timetable'
    }
    
    return render(request, 'admin_portal/timetable/index.html', context)

@login_required
@admin_required
def timetable_create(request):
    """View for creating a new timetable entry"""
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            try:
                timetable_entry = form.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Created new timetable entry: {timetable_entry.faculty_subject.faculty.user.full_name} - "
                    f"{timetable_entry.faculty_subject.subject.subject_name} on {timetable_entry.day_of_week}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, "Timetable entry created successfully.")
                return redirect('admin_portal:timetable')
            except Exception as e:
                logger.error(f"Error creating timetable entry: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating timetable entry: {str(e)}")
    else:
        # Try to get current academic year for default
        try:
            current_year = AcademicYear.objects.get(is_current=True)
            form = TimetableForm(initial={'academic_year': current_year})
        except AcademicYear.DoesNotExist:
            form = TimetableForm()
    
    # Get faculty assignments for the dropdown
    faculty_assignments = FacultySubject.objects.select_related(
        'faculty', 'faculty__user', 'subject', 'class_section', 'batch'
    ).order_by('faculty__user__full_name')
    
    # Day of week choices
    day_choices = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday')
    ]
    
    return render(request, 'admin_portal/timetable/create.html', {
        'form': form,
        'faculty_assignments': faculty_assignments,
        'day_choices': day_choices,
        'active_page': 'timetable'
    })

@login_required
@admin_required
def timetable_edit(request, timetable_id):
    """View for editing a timetable entry"""
    timetable_entry = get_object_or_404(Timetable, timetable_id=timetable_id)
    
    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=timetable_entry)
        if form.is_valid():
            try:
                timetable_entry = form.save()
                
                # Log the action
                log_admin_action(
                    request.user,
                    f"Updated timetable entry: {timetable_entry.faculty_subject.faculty.user.full_name} - "
                    f"{timetable_entry.faculty_subject.subject.subject_name} on {timetable_entry.day_of_week}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, "Timetable entry updated successfully.")
                return redirect('admin_portal:timetable')
            except Exception as e:
                logger.error(f"Error updating timetable entry: {str(e)}", exc_info=True)
                messages.error(request, f"Error updating timetable entry: {str(e)}")
    else:
        form = TimetableForm(instance=timetable_entry)
    
    # Get faculty assignments for the dropdown
    faculty_assignments = FacultySubject.objects.select_related(
        'faculty', 'faculty__user', 'subject', 'class_section', 'batch'
    ).order_by('faculty__user__full_name')
    
    # Day of week choices
    day_choices = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday')
    ]
    
    return render(request, 'admin_portal/timetable/edit.html', {
        'form': form,
        'timetable_entry': timetable_entry,
        'faculty_assignments': faculty_assignments,
        'day_choices': day_choices,
        'active_page': 'timetable'
    })

@login_required
@admin_required
def timetable_delete(request, timetable_id):
    """View for deleting a timetable entry"""
    timetable_entry = get_object_or_404(Timetable, timetable_id=timetable_id)
    
    if request.method == 'POST':
        try:
            # Store info for logging
            faculty_name = timetable_entry.faculty_subject.faculty.user.full_name
            subject_name = timetable_entry.faculty_subject.subject.subject_name
            day = timetable_entry.day_of_week
            
            # Delete the entry
            timetable_entry.delete()
            
            # Log the action
            log_admin_action(
                request.user,
                f"Deleted timetable entry: {faculty_name} - {subject_name} on {day}",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, "Timetable entry deleted successfully.")
            return redirect('admin_portal:timetable')
        except Exception as e:
            logger.error(f"Error deleting timetable entry: {str(e)}", exc_info=True)
            messages.error(request, f"Error deleting timetable entry: {str(e)}")
            return redirect('admin_portal:timetable_edit', timetable_id=timetable_id)
    
    return render(request, 'admin_portal/timetable/delete_confirm.html', {
        'timetable_entry': timetable_entry,
        'active_page': 'timetable'
    })

@login_required
@admin_required
def get_faculty_subjects(request):
    """AJAX view to get faculty subjects based on filters"""
    faculty_id = request.GET.get('faculty_id')
    academic_year_id = request.GET.get('academic_year_id')
    
    if not faculty_id:
        return JsonResponse([], safe=False)
    
    try:
        # Base query for faculty subjects
        faculty_subjects = FacultySubject.objects.filter(faculty_id=faculty_id)
        
        # Apply academic year filter if provided
        if academic_year_id:
            faculty_subjects = faculty_subjects.filter(academic_year_id=academic_year_id)
        
        # Select related fields for efficient querying
        faculty_subjects = faculty_subjects.select_related(
            'subject', 'class_section', 'batch'
        )
        
        # Format data for JSON response
        result = []
        for fs in faculty_subjects:
            class_section = fs.class_section.section_name if fs.class_section else "N/A"
            batch = f"Batch {fs.batch.batch_name}" if fs.batch else "N/A"
            
            result.append({
                'faculty_subject_id': fs.faculty_subject_id,
                'subject_name': fs.subject.subject_name,
                'subject_code': fs.subject.subject_code,
                'class_section': class_section,
                'batch': batch,
                'is_lab': fs.is_lab,
                'display_text': f"{fs.subject.subject_code} - {fs.subject.subject_name} ({class_section})"
            })
        
        return JsonResponse(result, safe=False)
    except Exception as e:
        logger.error(f"Error fetching faculty subjects: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@admin_required
def system_logs(request):
    """View for listing system logs with filtering and pagination"""
    # Get query parameters
    search_query = request.GET.get('search', '')
    user_filter = request.GET.get('user', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    page_number = request.GET.get('page', 1)
    
    # Base queryset with most recent logs first
    logs = SystemLog.objects.select_related('user').order_by('-created_at')
    
    # Apply filters
    if search_query:
        logs = logs.filter(
            Q(action__icontains=search_query) | 
            Q(details__icontains=search_query) |
            Q(user__full_name__icontains=search_query)
        )
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
        
    if action_filter:
        logs = logs.filter(action__icontains=action_filter)
        
    # Date range filtering
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            messages.warning(request, "Invalid 'from' date format. Using all dates.")
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            # Add one day to include entries from the end date
            date_to_obj = date_to_obj + datetime.timedelta(days=1)
            logs = logs.filter(created_at__date__lt=date_to_obj)
        except ValueError:
            messages.warning(request, "Invalid 'to' date format. Using all dates.")
    
    # Pagination
    paginator = Paginator(logs, 25)  # 25 logs per page
    page_obj = paginator.get_page(page_number)
    
    # Get all users for filter dropdown
    users = User.objects.filter(
        user_id__in=SystemLog.objects.values_list('user_id', flat=True).distinct()
    ).order_by('full_name')
    
    # Get common actions for filter dropdown
    common_actions = SystemLog.objects.values('action').annotate(
        count=Count('log_id')
    ).order_by('-count')[:20]
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'user_filter': user_filter,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
        'users': users,
        'common_actions': common_actions,
        'active_page': 'logs'
    }
    
    return render(request, 'admin_portal/logs/index.html', context)

@login_required
@admin_required
def export_system_logs(request):
    """View for exporting system logs as CSV"""
    # Get query parameters (same as in system_logs view)
    search_query = request.GET.get('search', '')
    user_filter = request.GET.get('user', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset with most recent logs first
    logs = SystemLog.objects.select_related('user').order_by('-created_at')
    
    # Apply the same filters as in the system_logs view
    if search_query:
        logs = logs.filter(
            Q(action__icontains=search_query) | 
            Q(details__icontains=search_query) |
            Q(user__full_name__icontains=search_query)
        )
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
        
    if action_filter:
        logs = logs.filter(action__icontains=action_filter)
        
    # Date range filtering
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            date_to_obj = date_to_obj + datetime.timedelta(days=1)
            logs = logs.filter(created_at__date__lt=date_to_obj)
        except ValueError:
            pass
    
    # Create the HttpResponse with CSV content
    response = HttpResponse(content_type='text/csv')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="system_logs_{timestamp}.csv"'
    
    # Write to CSV
    writer = csv.writer(response)
    writer.writerow(['Log ID', 'User', 'Action', 'Details', 'IP Address', 'Timestamp'])
    
    for log in logs:
        writer.writerow([
            log.log_id,
            log.user.full_name if log.user else 'Unknown',
            log.action,
            log.details,
            log.ip_address or 'N/A',
            log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response