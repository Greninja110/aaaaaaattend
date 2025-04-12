from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password
from authentication.models import Role, User
from core.models import Department
import logging
import random
from django.utils import timezone
from core.models import Department, ClassSection, Batch, Student
from lab_assistant_portal.models import LabAssistant

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Creates default users for each role in the system'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                self.stdout.write(self.style.NOTICE('Creating default roles...'))
                
                # Create default roles if they don't exist
                roles = {
                    'admin': 'Full system access',
                    'hod': 'Department head with department-wide access',
                    'faculty': 'Teacher with subject and class access',
                    'lab_assistant': 'Manages attendance exceptions and leave applications',
                    'student': 'Student with personal data access only'
                }
                
                for role_name, description in roles.items():
                    role, created = Role.objects.get_or_create(
                        role_name=role_name, 
                        defaults={'description': description}
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Created role: {role_name}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Role already exists: {role_name}'))
                
                # Get all roles
                admin_role = Role.objects.get(role_name='admin')
                hod_role = Role.objects.get(role_name='hod')
                faculty_role = Role.objects.get(role_name='faculty')
                lab_assistant_role = Role.objects.get(role_name='lab_assistant')
                student_role = Role.objects.get(role_name='student')
                
                # Create default users
                default_users = [
                    {
                        'username': 'admin',
                        'email': 'admin@mbit.edu.in',
                        'full_name': 'System Administrator',
                        'role': admin_role,
                        'password': '123'
                    },
                    {
                        'username': 'hod',
                        'email': 'hod@mbit.edu.in',
                        'full_name': 'Head of Department',
                        'role': hod_role,
                        'password': '123'
                    },
                    {
                        'username': 'faculty',
                        'email': 'faculty@mbit.edu.in',
                        'full_name': 'Faculty Member',
                        'role': faculty_role,
                        'password': '123'
                    },
                    {
                        'username': 'lab',
                        'email': 'lab_assistant@mbit.edu.in',
                        'full_name': 'Lab Assistant',
                        'role': lab_assistant_role,
                        'password': '123'
                    },
                    {
                        'username': 'student',
                        'email': 'student@mbit.edu.in',
                        'full_name': 'Student',
                        'role': student_role,
                        'password': '123'
                    }
                ]
                
                # Get a department
                department = Department.objects.first()
                if not department:
                    department = Department.objects.create(
                        department_name="Computer Engineering",
                        department_code="CE"
                    )
                
                # Get or create a class section
                class_section, _ = ClassSection.objects.get_or_create(
                    section_name="CE1", 
                    department=department
                )
                
                # Get or create a batch
                batch, _ = Batch.objects.get_or_create(batch_name="A")
                
                for user_data in default_users:
                    user, created = User.objects.get_or_create(
                        email=user_data['email'],
                        defaults={
                            'username': user_data['username'],
                            'full_name': user_data['full_name'],
                            'role': user_data['role'],
                            'password': make_password(user_data['password']),
                            'is_active': True
                        }
                    )
                    
                    if created:
                        self.stdout.write(self.style.SUCCESS(
                            f"Created user: {user_data['full_name']} ({user_data['email']}) with role {user_data['role'].role_name}"
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"User already exists: {user_data['email']}"
                        ))
                    
                    # Create role-specific profiles
                    if user_data['role'] == student_role:
                        # Create student record
                        Student.objects.get_or_create(
                            user=user,
                            defaults={
                                'roll_number': f"S{random.randint(10000, 99999)}",
                                'admission_year': 2023,
                                'dob': timezone.now().date() - timezone.timedelta(days=365*20),  # ~20 years old
                                'batch': batch,
                                'class_section': class_section,
                                'department': department,
                                'current_semester': 1,
                                'status': 'active'
                            }
                        )
                    elif user_data['role'] == lab_assistant_role:
                        # Create lab assistant record
                        LabAssistant.objects.get_or_create(
                            user=user,
                            defaults={
                                'department': department,
                                'joining_year': 2023,
                                'status': 'active'
                            }
                        )
                
                self.stdout.write(self.style.SUCCESS('Successfully created default users'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating default users: {str(e)}'))
            logger.exception('Error in create_default_users command')
            raise