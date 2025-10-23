# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('evaluations', '0002_evaluation_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluation',
            name='technologies',
            field=models.ManyToManyField(blank=True, related_name='evaluation_technologies', to='core.technology', verbose_name='Technologies'),
        ),
    ]
