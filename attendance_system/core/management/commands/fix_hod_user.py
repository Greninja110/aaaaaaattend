from django.core.management.base import BaseCommand
from django.db import transaction
from authentication.models import User
from core.models import Department, Faculty, Subject
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix HOD user by creating Faculty record and assigning department'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                self.stdout.write(self.style.NOTICE('Fixing HOD user setup...'))
                
                # Get the HOD user
                hod_user = User.objects.get(email='hod@mbit.edu.in')
                
                # Get or create a department
                department, created = Department.objects.get_or_create(
                    department_code='CE',
                    defaults={
                        'department_name': 'Computer Engineering',
                        'department_short_name': 'CE'
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS('Created department: Computer Engineering'))
                else:
                    self.stdout.write(self.style.WARNING('Department already exists: Computer Engineering'))
                
                # Create Faculty record for HOD user
                faculty, created = Faculty.objects.get_or_create(
                    user=hod_user,
                    defaults={
                        'employee_id': 'HOD001',
                        'designation': 'Head of Department',
                        'department': department,
                        'dob': timezone.now().date() - timezone.timedelta(days=365*35),  # ~35 years old
                        'joining_year': 2020,
                        'weekly_hours_limit': 40,
                        'current_weekly_hours': 0,
                        'status': 'active'
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created Faculty record for HOD user: {hod_user.username}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Faculty record already exists for HOD user: {hod_user.username}'))
                
                # Update department to assign HOD
                department.hod_id = faculty.faculty_id
                department.save()
                
                self.stdout.write(self.style.SUCCESS(f'Assigned {hod_user.full_name} as HOD of {department.department_name}'))
                
                # Create a sample subject for the HOD faculty
                subject, created = Subject.objects.get_or_create(
                    subject_name='Data Structures',
                    subject_code='CS101',
                    defaults={
                        'department': department,
                        'semester': 3,
                        'credits': 4,
                        'description': 'Introduction to Data Structures and Algorithms'
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS('Created sample subject: Data Structures'))
                
                # Assign subject to faculty
                faculty.subjects.add(subject)
                
                self.stdout.write(self.style.SUCCESS('Successfully fixed HOD user setup'))
                
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('HOD user not found. Please run create_default_users first.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fixing HOD user: {str(e)}'))
            logger.exception('Error in fix_hod_user command')
            raise