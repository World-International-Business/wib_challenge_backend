import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0020_offerconversation_conversationmessage'),
        ('organizations', '0010_organization_auto_analyze_applications_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecruitmentEmailInbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host', models.CharField(max_length=253)),
                ('username', models.CharField(max_length=254)),
                ('secret', models.TextField()),
                ('folder', models.CharField(default='INBOX', max_length=255)),
                ('enabled', models.BooleanField(default=False)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('last_sync_at', models.DateTimeField(blank=True, null=True)),
                ('next_sync_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('error_code', models.CharField(blank=True, max_length=50)),
                ('failures', models.PositiveIntegerField(default=0)),
                ('uid_validity', models.CharField(blank=True, max_length=30)),
                ('last_uid', models.PositiveBigIntegerField(default=0)),
                ('lease_token', models.CharField(blank=True, max_length=36)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('default_offer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='jobs.joboffer')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_inboxes', to='organizations.organization')),
            ],
        ),
        migrations.CreateModel(
            name='RecruitmentEmailMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fingerprint', models.CharField(max_length=64)),
                ('uid_validity', models.CharField(max_length=30)),
                ('uid', models.PositiveBigIntegerField()),
                ('sender', models.CharField(blank=True, max_length=254)),
                ('subject', models.CharField(blank=True, max_length=255)),
                ('raw_secret', models.TextField(blank=True)),
                ('status', models.CharField(default='unassigned', max_length=30)),
                ('error_code', models.CharField(blank=True, max_length=50)),
                ('analysis_state', models.CharField(db_index=True, default='manual', max_length=20)),
                ('analysis_attempts', models.PositiveIntegerField(default=0)),
                ('analysis_next_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('analysis_locked_until', models.DateTimeField(blank=True, null=True)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('application', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='jobs.jobapplication')),
                ('inbox', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='organizations.recruitmentemailinbox')),
            ],
            options={
                'ordering': ['-received_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='recruitmentemailinbox',
            constraint=models.UniqueConstraint(fields=('organization', 'host', 'username', 'folder'), name='unique_recruitment_inbox'),
        ),
        migrations.AddConstraint(
            model_name='recruitmentemailmessage',
            constraint=models.UniqueConstraint(fields=('inbox', 'fingerprint'), name='unique_recruitment_email_content'),
        ),
        migrations.AddConstraint(
            model_name='recruitmentemailmessage',
            constraint=models.UniqueConstraint(fields=('inbox', 'uid_validity', 'uid'), name='unique_recruitment_email_uid'),
        ),
    ]
