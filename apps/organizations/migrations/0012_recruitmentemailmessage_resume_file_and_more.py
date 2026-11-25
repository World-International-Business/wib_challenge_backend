import django.db.models.deletion
import services.email_storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0020_offerconversation_conversationmessage'),
        ('organizations', '0011_recruitmentemailinbox_recruitmentemailmessage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recruitmentemailmessage',
            name='resume_file',
            field=models.FileField(blank=True, storage=services.email_storage.RecruitmentResumeStorage(), upload_to=''),
        ),
        migrations.AlterField(
            model_name='recruitmentemailmessage',
            name='application',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_receipt', to='jobs.jobapplication'),
        ),
    ]
