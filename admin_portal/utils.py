import logging
import csv
import io
import pandas as pd
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from authentication.models import User, Role
from core.models import Department, SystemLog
from .models import BulkImportLog
import datetime

from core.models import Department, Faculty, Student, SystemLog, ClassSection, Batch
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def get_current_academic_year():
    """Helper to get the current academic year"""
    from core.models import AcademicYear
    try:
        return AcademicYear.objects.get(is_current=True)
    except AcademicYear.DoesNotExist:
        logger.warning("No current academic year set in the system")
        return None

def log_admin_action(user, action, details=None, ip_address=None):
    """Helper to log admin actions"""
    try:
        SystemLog.objects.create(
            user=user,
            action=action,
            details=details,
            ip_address=ip_address
        )
        logger.info(f"Admin action logged: {action} by {user.email}")
    except Exception as e:
        logger.error(f"Failed to log admin action: {str(e)}")

def get_system_stats():
    """Helper to get system statistics for dashboard"""
    from django.db.models import Count
    
    try:
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_departments': Department.objects.count(),
            'user_distribution': User.objects.values('role__role_name').annotate(count=Count('user_id'))
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return {}

def handle_uploaded_csv(file, import_type, user):
    """Process and validate CSV uploads for bulk import"""
    try:
        # Read the CSV file
        csv_data = file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_data))
        
        # Create a log entry
        import_log = BulkImportLog.objects.create(
            import_type=import_type,
            file_name=file.name,
            total_records=len(df),
            user=user
        )
        
        # Process based on import type
        if import_type == 'students':
            results = process_student_import(df, user, import_log)
        elif import_type == 'faculty':
            results = process_faculty_import(df, user, import_log)
        else:
            raise ValueError(f"Unknown import type: {import_type}")
            
        return results
    
    except Exception as e:
        logger.error(f"Error in CSV import: {str(e)}", exc_info=True)
        if 'import_log' in locals():
            import_log.error_details = str(e)
            import_log.failed_records = import_log.total_records
            import_log.save()
        return {
            'success': False,
            'error': str(e),
            'records_processed': 0,
            'records_failed': import_log.total_records if 'import_log' in locals() else 0
        }

def process_student_import(df, user, import_log):
    """Process student import from DataFrame"""
    # Placeholder - will implement in Step 2
    pass

def process_faculty_import(df, user, import_log):
    """Process faculty import from DataFrame"""
    # Placeholder - will implement in Step 2
    pass

def process_student_import(df, user, import_log):
    """Process student import from DataFrame"""
    try:
        with transaction.atomic():
            # Get the student role
            student_role = Role.objects.get(role_name='student')
            
            # Get batch A as default
            default_batch = Batch.objects.filter(batch_name='A').first()
            if not default_batch:
                default_batch = Batch.objects.first()
            
            # Initialize counters
            successful = 0
            failed = 0
            error_details = []
            
            # Process each row
            for idx, row in df.iterrows():
                try:
                    # Validate required fields
                    required_fields = ['email', 'full_name', 'username', 'roll_number', 
                                      'admission_year', 'department_code', 'current_semester']
                    
                    for field in required_fields:
                        if field not in row or pd.isna(row[field]):
                            raise ValidationError(f"Missing required field: {field}")
                    
                    # Check if email already exists
                    if User.objects.filter(email=row['email']).exists():
                        raise ValidationError(f"Email already exists: {row['email']}")
                    
                    # Check if username already exists
                    if User.objects.filter(username=row['username']).exists():
                        raise ValidationError(f"Username already exists: {row['username']}")
                    
                    # Check if roll number already exists
                    if Student.objects.filter(roll_number=row['roll_number']).exists():
                        raise ValidationError(f"Roll number already exists: {row['roll_number']}")
                    
                    # Get department by code
                    try:
                        department = Department.objects.get(department_code=row['department_code'])
                    except Department.DoesNotExist:
                        raise ValidationError(f"Department not found: {row['department_code']}")
                    
                    # Get class section
                    section_name = row.get('section', 'A')
                    class_section = ClassSection.objects.filter(
                        section_name__iexact=f"{department.department_code}{section_name}",
                        department=department
                    ).first()
                    
                    if not class_section:
                        # Create class section if it doesn't exist
                        class_section = ClassSection.objects.create(
                            section_name=f"{department.department_code}{section_name}",
                            department=department
                        )
                    
                    # Parse date of birth if provided
                    dob = None
                    if 'dob' in row and not pd.isna(row['dob']):
                        try:
                            dob = datetime.datetime.strptime(str(row['dob']), '%Y-%m-%d').date()
                        except ValueError:
                            dob = None
                    
                    # Create user
                    user = User.objects.create(
                        email=row['email'],
                        username=row['username'],
                        full_name=row['full_name'],
                        role=student_role,
                        is_active=True,
                        enrollment_number=row.get('enrollment_number', row['roll_number'])
                    )
                    
                    # Set default password
                    default_password = '123'  # This should come from settings
                    user.set_password(default_password)
                    user.save()
                    
                    # Create student
                    Student.objects.create(
                        user=user,
                        roll_number=row['roll_number'],
                        admission_year=int(row['admission_year']),
                        department=department,
                        current_semester=int(row['current_semester']),
                        class_section=class_section,
                        batch=default_batch,
                        dob=dob,
                        status='active'
                    )
                    
                    successful += 1
                except Exception as e:
                    failed += 1
                    error_details.append(f"Row {idx+2}: {str(e)}")
                    logger.error(f"Error processing student row {idx+2}: {str(e)}")
            
            # Update import log
            import_log.successful_records = successful
            import_log.failed_records = failed
            import_log.error_details = "\n".join(error_details) if error_details else None
            import_log.save()
            
            # Log the action
            SystemLog.objects.create(
                user=user,
                action=f"Bulk imported {successful} students",
                details=f"Success: {successful}, Failed: {failed}",
                ip_address=None
            )
            
            return {
                'success': True,
                'records_processed': successful,
                'records_failed': failed,
                'log_id': import_log.import_id
            }
    except Exception as e:
        logger.error(f"Error in student import: {str(e)}", exc_info=True)
        import_log.error_details = str(e)
        import_log.failed_records = import_log.total_records
        import_log.save()
        return {
            'success': False,
            'error': str(e),
            'records_processed': 0,
            'records_failed': import_log.total_records,
            'log_id': import_log.import_id
        }

def process_faculty_import(df, user, import_log):
    """Process faculty import from DataFrame"""
    try:
        with transaction.atomic():
            # Get the faculty role
            faculty_role = Role.objects.get(role_name='faculty')
            
            # Initialize counters
            successful = 0
            failed = 0
            error_details = []
            
            # Process each row
            for idx, row in df.iterrows():
                try:
                    # Validate required fields
                    required_fields = ['email', 'full_name', 'username', 'employee_id', 
                                      'department_code', 'designation', 'joining_year']
                    
                    for field in required_fields:
                        if field not in row or pd.isna(row[field]):
                            raise ValidationError(f"Missing required field: {field}")
                    
                    # Check if email already exists
                    if User.objects.filter(email=row['email']).exists():
                        raise ValidationError(f"Email already exists: {row['email']}")
                    
                    # Check if username already exists
                    if User.objects.filter(username=row['username']).exists():
                        raise ValidationError(f"Username already exists: {row['username']}")
                    
                    # Check if employee ID already exists
                    if Faculty.objects.filter(employee_id=row['employee_id']).exists():
                        raise ValidationError(f"Employee ID already exists: {row['employee_id']}")
                    
                    # Get department by code
                    try:
                        department = Department.objects.get(department_code=row['department_code'])
                    except Department.DoesNotExist:
                        raise ValidationError(f"Department not found: {row['department_code']}")
                    
                    # Parse date of birth if provided
                    dob = None
                    if 'dob' in row and not pd.isna(row['dob']):
                        try:
                            dob = datetime.datetime.strptime(str(row['dob']), '%Y-%m-%d').date()
                        except ValueError:
                            dob = None
                    
                    # Create user
                    user = User.objects.create(
                        email=row['email'],
                        username=row['username'],
                        full_name=row['full_name'],
                        role=faculty_role,
                        is_active=True
                    )
                    
                    # Set default password
                    default_password = '123'  # This should come from settings
                    user.set_password(default_password)
                    user.save()
                    
                    # Create faculty
                    Faculty.objects.create(
                        user=user,
                        employee_id=row['employee_id'],
                        department=department,
                        designation=row['designation'],
                        joining_year=int(row['joining_year']),
                        dob=dob,
                        status='active'
                    )
                    
                    successful += 1
                except Exception as e:
                    failed += 1
                    error_details.append(f"Row {idx+2}: {str(e)}")
                    logger.error(f"Error processing faculty row {idx+2}: {str(e)}")
            
            # Update import log
            import_log.successful_records = successful
            import_log.failed_records = failed
            import_log.error_details = "\n".join(error_details) if error_details else None
            import_log.save()
            
            # Log the action
            SystemLog.objects.create(
                user=user,
                action=f"Bulk imported {successful} faculty",
                details=f"Success: {successful}, Failed: {failed}",
                ip_address=None
            )
            
            return {
                'success': True,
                'records_processed': successful,
                'records_failed': failed,
                'log_id': import_log.import_id
            }
    except Exception as e:
        logger.error(f"Error in faculty import: {str(e)}", exc_info=True)
        import_log.error_details = str(e)
        import_log.failed_records = import_log.total_records
        import_log.save()
        return {
            'success': False,
            'error': str(e),
            'records_processed': 0,
            'records_failed': import_log.total_records,
            'log_id': import_log.import_id
        }