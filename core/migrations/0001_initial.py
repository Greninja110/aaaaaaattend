# Generated by Django 4.2.10 on 2025-03-20 04:31

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AcademicYear',
            fields=[
                ('academic_year_id', models.AutoField(primary_key=True, serialize=False)),
                ('year_start', models.IntegerField()),
                ('year_end', models.IntegerField()),
                ('is_current', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'academic_years',
            },
        ),
        migrations.CreateModel(
            name='Batch',
            fields=[
                ('batch_id', models.AutoField(primary_key=True, serialize=False)),
                ('batch_name', models.CharField(max_length=1, unique=True)),
            ],
            options={
                'db_table': 'batches',
            },
        ),
        migrations.CreateModel(
            name='ClassSection',
            fields=[
                ('class_section_id', models.AutoField(primary_key=True, serialize=False)),
                ('section_name', models.CharField(max_length=10)),
            ],
            options={
                'db_table': 'class_sections',
            },
        ),
        migrations.CreateModel(
            name='Department',
            fields=[
                ('department_id', models.AutoField(primary_key=True, serialize=False)),
                ('department_name', models.CharField(max_length=100)),
                ('department_code', models.CharField(max_length=10, unique=True)),
                ('hod_id', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'departments',
            },
        ),
        migrations.CreateModel(
            name='SystemLog',
            fields=[
                ('log_id', models.AutoField(primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=100)),
                ('details', models.TextField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'system_logs',
            },
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('student_id', models.AutoField(primary_key=True, serialize=False)),
                ('roll_number', models.CharField(max_length=20, unique=True)),
                ('admission_year', models.IntegerField(default=2023)),
                ('dob', models.DateField(blank=True, null=True)),
                ('current_semester', models.IntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(8)])),
                ('section', models.CharField(blank=True, max_length=5, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('graduated', 'Graduated'), ('suspended', 'Suspended')], default='active', max_length=20)),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.batch')),
                ('class_section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.classsection')),
                ('department', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='core.department')),
                ('user', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'students',
            },
        ),
        migrations.CreateModel(
            name='Faculty',
            fields=[
                ('faculty_id', models.AutoField(primary_key=True, serialize=False)),
                ('employee_id', models.CharField(max_length=20, unique=True)),
                ('dob', models.DateField(blank=True, null=True)),
                ('joining_year', models.IntegerField(default=2023)),
                ('designation', models.CharField(default='Assistant Professor', max_length=100)),
                ('weekly_hours_limit', models.IntegerField(default=40)),
                ('current_weekly_hours', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('on_leave', 'On Leave')], default='active', max_length=20)),
                ('department', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='core.department')),
                ('user', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'faculty',
            },
        ),
        migrations.AddField(
            model_name='classsection',
            name='department',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='core.department'),
        ),
    ]
