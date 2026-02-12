from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0005_alter_evaluation_evaluation_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evaluationinvitation',
            name='candidate',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='evaluations.candidate', verbose_name='Candidat'),
        ),
    ]
