# Generated manually for renaming category to poste

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_remove_joboffer_salary_max_and_more'),
    ]

    operations = [
        # Rename category to poste
        migrations.RenameField(
            model_name='joboffer',
            old_name='category',
            new_name='poste',
        ),
        # Add new fields
        migrations.AddField(
            model_name='joboffer',
            name='attachments',
            field=models.ImageField(blank=True, null=True, upload_to='job_attachments/', verbose_name='Image/Flyer'),
        ),
        migrations.AddField(
            model_name='joboffer',
            name='required_documents',
            field=models.JSONField(blank=True, default=list, verbose_name='Documents requis'),
        ),
    ]
