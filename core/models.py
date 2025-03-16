from django.db import models

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