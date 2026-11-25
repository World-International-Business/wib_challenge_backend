from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0009_organizationchannelcredential'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='auto_analyze_applications',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='notify_blocking_cases',
            field=models.BooleanField(default=True),
        ),
    ]
