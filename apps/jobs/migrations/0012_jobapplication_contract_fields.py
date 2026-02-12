from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0011_joboffer_evaluations_and_jobapplicationevaluation'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobapplication',
            name='contract_status',
            field=models.CharField(
                choices=[
                    ('not_prepared', 'Non préparé'),
                    ('sent', 'Envoyé'),
                    ('signed', 'Signé'),
                    ('rejected', 'Refusé'),
                    ('expired', 'Expiré'),
                ],
                default='not_prepared',
                max_length=20,
                verbose_name='Statut du contrat',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='contract_file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='contracts/',
                verbose_name='Contrat (PDF)',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='signed_contract_file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='contracts/signed/',
                verbose_name='Contrat signé (PDF)',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='contract_token',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                max_length=128,
                verbose_name='Token contrat',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='contract_token_expires_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Expiration token contrat',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='contract_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Envoyé le',
            ),
        ),
        migrations.AddField(
            model_name='jobapplication',
            name='contract_signed_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Signé le',
            ),
        ),
    ]
