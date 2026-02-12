from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0010_alter_jobapplication_source'),
        ('evaluations', '0006_alter_evaluationinvitation_candidate_to_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='joboffer',
            name='technical_evaluation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_offers_technical', to='evaluations.evaluation', verbose_name='Évaluation technique'),
        ),
        migrations.AddField(
            model_name='joboffer',
            name='psychotech_evaluation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_offers_psychotech', to='evaluations.evaluation', verbose_name='Évaluation psychotechnique'),
        ),
        migrations.AddField(
            model_name='joboffer',
            name='personality_evaluation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_offers_personality', to='evaluations.evaluation', verbose_name='Évaluation de personnalité'),
        ),
        migrations.CreateModel(
            name='JobApplicationEvaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')),
                ('status', models.CharField(choices=[('assigned', 'Assignée'), ('started', 'Commencée'), ('completed', 'Terminée')], default='assigned', max_length=20, verbose_name='Statut')),
                ('score', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='Score')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Terminé le')),
                ('evaluation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_application_evaluations', to='evaluations.evaluation', verbose_name='Évaluation')),
                ('invitation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job_application_evaluations', to='evaluations.evaluationinvitation', verbose_name='Invitation')),
                ('job_application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='jobs.jobapplication', verbose_name='Candidature')),
            ],
            options={
                'verbose_name': 'Évaluation de candidature',
                'verbose_name_plural': 'Évaluations de candidatures',
                'ordering': ['-created_at'],
                'unique_together': {('job_application', 'evaluation')},
            },
        ),
    ]
