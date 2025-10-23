# Migration de données pour remplir le champ technologies des évaluations existantes

from django.db import migrations


def populate_technologies(apps, schema_editor):
    """Copie les technologies déduites des questions vers le champ technologies"""
    Evaluation = apps.get_model('evaluations', 'Evaluation')
    Technology = apps.get_model('core', 'Technology')
    
    for evaluation in Evaluation.objects.all():
        # Récupérer les technologies uniques à partir des questions de l'évaluation
        tech_ids = evaluation.questions.values_list('technology_id', flat=True).distinct()
        # Filtrer les None
        tech_ids = [tid for tid in tech_ids if tid is not None]
        
        if tech_ids:
            # Ajouter ces technologies au champ ManyToMany
            technologies = Technology.objects.filter(id__in=tech_ids)
            evaluation.technologies.set(technologies)


def reverse_populate_technologies(apps, schema_editor):
    """Fonction inverse (vider le champ technologies)"""
    Evaluation = apps.get_model('evaluations', 'Evaluation')
    for evaluation in Evaluation.objects.all():
        evaluation.technologies.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0003_evaluation_technologies'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_technologies, reverse_populate_technologies),
    ]
