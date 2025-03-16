from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_fix_table_names'),
    ]

    operations = [
        migrations.RunSQL(
            # This SQL doesn't actually do anything - it's just a placeholder
            "SELECT 1;",
            "SELECT 1;"
        ),
    ]