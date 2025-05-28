from django.core.management.base import BaseCommand
from django.db.models import Q
from challenges.models import Submission, PersonalityChallenge
from challenges.corrector import correct_submission, correct_personality_challenge


class Command(BaseCommand):
    help = 'Corrige toutes les soumissions et défis de personnalité en attente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Corriger toutes les soumissions, même celles déjà corrigées',
        )
        
        parser.add_argument(
            '--submission-id',
            type=int,
            help='ID d\'une soumission spécifique à corriger',
        )
        
        parser.add_argument(
            '--personality-id',
            type=int,
            help='ID d\'un défi de personnalité spécifique à corriger',
        )

    def handle(self, *args, **options):
        all_corrections = options['all']
        submission_id = options.get('submission_id')
        personality_id = options.get('personality_id')
        
        # Correction d'une soumission spécifique
        if submission_id:
            try:
                submission = Submission.objects.get(id=submission_id)
                self.stdout.write(self.style.SUCCESS(f'Correction de la soumission #{submission.id} - {submission.candidate} - {submission.challenge}'))
                correct_submission(submission)
                self.stdout.write(self.style.SUCCESS(f'Soumission #{submission.id} corrigée avec succès.'))
                return
            except Submission.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Soumission avec ID {submission_id} introuvable.'))
                return
        
        # Correction d'un défi de personnalité spécifique
        if personality_id:
            try:
                challenge = PersonalityChallenge.objects.get(id=personality_id)
                self.stdout.write(self.style.SUCCESS(f'Correction du défi de personnalité #{challenge.id} - {challenge.candidate}'))
                correct_personality_challenge(challenge)
                self.stdout.write(self.style.SUCCESS(f'Défi de personnalité #{challenge.id} corrigé avec succès.'))
                return
            except PersonalityChallenge.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Défi de personnalité avec ID {personality_id} introuvable.'))
                return
        
        # Correction de toutes les soumissions en attente
        submissions_query = Submission.objects.all() if all_corrections else Submission.objects.filter(status=Submission.CorrectionStatus.PENDING)
        submissions_count = submissions_query.count()
        
        if submissions_count > 0:
            self.stdout.write(f'Correction de {submissions_count} soumissions...')
            
            for i, submission in enumerate(submissions_query, 1):
                self.stdout.write(f'[{i}/{submissions_count}] Correction de la soumission #{submission.id} - {submission.candidate} - {submission.challenge}')
                try:
                    correct_submission(submission)
                    self.stdout.write(self.style.SUCCESS(f'✓ Soumission #{submission.id} corrigée avec succès.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'✗ Erreur lors de la correction de la soumission #{submission.id}: {str(e)}'))
        else:
            self.stdout.write('Aucune soumission à corriger.')
        
        # Correction de tous les défis de personnalité non corrigés
        personalities_query = PersonalityChallenge.objects.all() if all_corrections else PersonalityChallenge.objects.filter(
            Q(is_passed=True) & Q(corrected=False)
        )
        personalities_count = personalities_query.count()
        
        if personalities_count > 0:
            self.stdout.write(f'Correction de {personalities_count} défis de personnalité...')
            
            for i, challenge in enumerate(personalities_query, 1):
                self.stdout.write(f'[{i}/{personalities_count}] Correction du défi de personnalité #{challenge.id} - {challenge.candidate}')
                try:
                    correct_personality_challenge(challenge)
                    self.stdout.write(self.style.SUCCESS(f'✓ Défi de personnalité #{challenge.id} corrigé avec succès.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'✗ Erreur lors de la correction du défi de personnalité #{challenge.id}: {str(e)}'))
        else:
            self.stdout.write('Aucun défi de personnalité à corriger.')

        self.stdout.write(self.style.SUCCESS('Toutes les corrections ont été effectuées.'))