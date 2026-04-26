# Generated migration for adding new fields to Student model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consultorio', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='attendance_days',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Dias de Asistencia'),
        ),
        migrations.AddField(
            model_name='student',
            name='legal_office',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Consultorio'),
        ),
        migrations.AddField(
            model_name='student',
            name='semester',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Semestre'),
        ),
    ]
