from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challenges', '0005_interview_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='minimum_technical_question_count',
            field=models.PositiveIntegerField(
                default=20,
                verbose_name='Nombre minimum de questions techniques',
            ),
        ),
    ]
