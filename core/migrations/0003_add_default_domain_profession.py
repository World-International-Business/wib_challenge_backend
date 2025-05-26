

from django.db import migrations
from django.db import models
import django.db.models.deletion


def create_default_domain_and_assign(apps, schema_editor):
    Domain = apps.get_model('core', 'Domain')
    Profession = apps.get_model('core', 'Profession')

    default_domain = Domain.objects.create(
        name="Autres",
        description="Domaine général pour les professions non spécifiées"
    )

    Profession.objects.update(domain=default_domain)


def reverse_migration(apps, schema_editor):
    Domain = apps.get_model('core', 'Domain')
    Domain.objects.filter(name="Autres").delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0002_domain_profession_domain'),
    ]

    operations = [
        migrations.RunPython(
            create_default_domain_and_assign, reverse_migration),
        migrations.AlterField(
            model_name='profession',
            name='domain',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='professions', to='core.domain', verbose_name='Domaine'),
        ),
    ]
