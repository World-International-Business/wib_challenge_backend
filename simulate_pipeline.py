# -*- coding: utf-8 -*-
"""Simulation du pipeline complet post-publication d'une offre.

Joue les vrais endpoints DRF : candidatures -> présélection -> évaluations ->
entretien -> acceptation -> contrat -> signature OTP.
À lancer avec :  python manage.py shell < simulate_pipeline.py
(emails capturés en locmem, rien n'est réellement envoyé)
"""
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

from apps.accounts.models import User
from apps.evaluations.models import Evaluation, EvaluationInvitation, Submission, SubmissionAttempt
from apps.jobs.models import JobApplication, JobApplicationEvaluation, JobCategory, JobOffer
from apps.organizations.models import Organization
from apps.questions.models import Question
from services.offer_distribution import publish_offer

PASS = []
FAIL = []


def step(title):
    print('\n' + '=' * 70)
    print(f'>> {title}')
    print('=' * 70)


def check(label, ok, extra=''):
    (PASS if ok else FAIL).append(label)
    print(f"   [{'OK' if ok else 'KO'}] {label} {extra}")


def api(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def last_code():
    body = mail.outbox[-1].body
    m = re.search(r'(\d{6})', body)
    return m.group(1) if m else None


# ---------------------------------------------------------------- setup
step('SETUP — organisation, recruteur, offre publiée, évaluations')

suffix = uuid.uuid4().hex[:6]
recruiter = User.objects.create_user(
    email=f'rh.{suffix}@wib-sim.local', password='sim-pass-123',
    first_name='Awa', last_name='Ngono', role=User.Roles.ORGANIZATION)
org = Organization.objects.create(
    account=recruiter, name='WIB Simulation SARL', country='Cameroun',
    city='Douala', linkedin_page_url='https://www.linkedin.com/company/wib-simulation',
    preferred_channels=['linkedin', 'emploi_cm'])
print(f"   Recruteur : {recruiter.email} | Org : {org.name}")

category, _ = JobCategory.objects.get_or_create(title='Développeur Backend')

evals = {}
for etype, title in (('technical', 'Test technique Python/Django'),
                     ('psychotech', 'Test psychotechnique'),
                     ('personality', 'Test de personnalité')):
    ev = Evaluation.objects.create(
        title=f'{title} (sim {suffix})', publisher=recruiter,
        evaluation_type=etype, is_active=True, archived=False,
        difficulty='intermediate')
    q = Question.objects.create(
        title=f'Question {etype}', explanation='explication', difficulty='medium',
        status=Question.Status.PUBLISHED, publisher=recruiter, weight=100)
    ev.questions.add(q)
    evals[etype] = ev

offer = JobOffer.objects.create(
    title=f'Développeur Backend Senior (sim {suffix})', company=org, poste=category,
    description='Concevoir et maintenir les APIs backend.',
    responsibilities='Développement, revues de code, mentorat.',
    requirements='3+ ans Python/Django, PostgreSQL, Docker.',
    benefits='Mutuelle, télétravail partiel, formation.',
    salary='450000-650000', currency='XAF', job_type='cdi',
    experience_level='senior', location='Douala', remote_allowed=True,
    required_documents=['cv', 'cover_letter'],
    status=JobOffer.Status.DRAFT,
    technical_evaluation=evals['technical'],
    psychotech_evaluation=evals['psychotech'],
    personality_evaluation=evals['personality'])

step('PUBLICATION — publish_offer() diffuse sur les canaux')
pub = publish_offer(offer)
offer.refresh_from_db()
for ch in pub['channels']:
    print(f"   canal {ch['name']:<14} -> {ch['state']} {ch.get('error') or ch.get('url') or ''}")
check('offre publiée', offer.status == 'published', f"({offer.published_at})")

# ---------------------------------------------------------------- candidats
step('CANDIDATURES — 3 candidats postulent via POST /offers/{id}/apply/')
candidates = []
for i, (first, last, score) in enumerate([
        ('Junior', 'Faible', 30), ('Awa', 'Candidate', 85), ('Marc', 'Excellent', 92)], 1):
    u = User.objects.create_user(
        email=f'cand{i}.{suffix}@wib-sim.local', password='cand-pass',
        first_name=first, last_name=last, role=User.Roles.USER)
    c = api(u)
    cv = SimpleUploadedFile(f'cv_{first}.pdf', b'%PDF-1.4 fake cv', content_type='application/pdf')
    r = c.post(f'/api/jobs/offers/{offer.pk}/apply/',
               {'applicant_name': f'{first} {last}',
                'applicant_email': u.email,
                'cover_letter': f'Je suis très motivé(e) {first}.',
                'resume': cv}, format='multipart')
    if r.status_code != 201:
        print('   Réponse erreur :', getattr(r, 'data', r.content))
    check(f'candidature {first} {last}', r.status_code == 201, f'(HTTP {r.status_code})')
    app = JobApplication.objects.get(job_offer=offer, user=u)
    app.ai_analysis = f'Analyse IA simulée : profil {"moyen" if score < 50 else "fort"}.'
    app.ai_decision = score >= 50
    app.save(update_fields=['ai_analysis', 'ai_decision'])
    candidates.append({'user': u, 'client': c, 'app': app, 'score': score})

rh = api(recruiter)
r = rh.get(f'/api/jobs/offers/{offer.pk}/applications/')
stats = r.data.get('statistics', {})
print(f"   Statistiques : {stats}")
check('3 candidatures reçues', stats.get('total') == 3, str(stats))

# ---------------------------------------------------------------- présélection
step('PRÉSÉLECTION — le RH passe en shortlisted / rejected')
for c in candidates:
    target = 'shortlisted' if c['score'] >= 50 else 'rejected'
    r = rh.patch(f"/api/jobs/applications/{c['app'].pk}/update-status/",
                 {'status': target, 'reason': 'Décision RH simulée',
                  'expected_version': c['app'].decision_version}, format='json')
    check(f"{c['app'].applicant_name} -> {target}",
          r.status_code == 200 and r.data.get('status') == target,
          f"(HTTP {r.status_code})")
    c['app'].refresh_from_db()

# ---------------------------------------------------------------- évaluations
step('ÉVALUATIONS — assignation des 3 tests puis résultats')
shortlisted = [c for c in candidates if c['app'].status == 'shortlisted']
for c in shortlisted:
    r = rh.post(f"/api/jobs/applications/{c['app'].pk}/assign-evaluations/")
    check(f"évaluations assignées à {c['app'].applicant_name}",
          r.status_code == 200, f"(HTTP {r.status_code})")

    # Le candidat passe les 3 évaluations (simulé au niveau modèles)
    for jae in JobApplicationEvaluation.objects.filter(job_application=c['app']):
        ev = jae.evaluation
        attempt = SubmissionAttempt.objects.filter(
            evaluation=ev,
            participant__candidate__email=c['app'].applicant_email).first()
        if not attempt:
            continue
        sub = Submission.objects.create(score=c['score'])
        attempt.submission = sub
        attempt.is_completed = True
        attempt.ended_at = timezone.now()
        attempt.save(update_fields=['submission', 'is_completed', 'ended_at'])
        jae.status = 'completed'
        jae.score = sub.score
        jae.completed_at = timezone.now()
        jae.save(update_fields=['status', 'score', 'completed_at'])

    r = rh.get(f"/api/jobs/applications/{c['app'].pk}/evaluation-results/")
    print(f"   {c['app'].applicant_name} : globalScore={r.data.get('globalScore')}")
    for e in r.data.get('evaluations', []):
        print(f"      - {e['title']} : {e['status']} score={e['score']}/{e['maxScore']} "
              f"moy={e['averageOn20']}")

# ---------------------------------------------------------------- entretien
step('ENTRETIEN — créneaux proposés puis réservation par le candidat')
winner = max(shortlisted, key=lambda c: c['score'])
slots = [
    {'starts_at': (timezone.now() + timedelta(days=2, hours=9)).isoformat(),
     'ends_at': (timezone.now() + timedelta(days=2, hours=10)).isoformat()},
    {'starts_at': (timezone.now() + timedelta(days=3, hours=14)).isoformat(),
     'ends_at': (timezone.now() + timedelta(days=3, hours=15)).isoformat()},
]
r = rh.post(f"/api/jobs/applications/{winner['app'].pk}/interview-booking/", {'slots': slots}, format='json')
check('créneaux d\'entretien créés', r.status_code == 201, f"(HTTP {r.status_code})")
token = r.data['token']

r = winner['client'].get(f'/api/jobs/interview-slots/{token}/')
avail = r.data.get('slots', [])
print(f"   Candidats voit {len(avail)} créneau(x) disponible(s)")
check('créneaux visibles publiquement', r.status_code == 200 and len(avail) == 2)

r = winner['client'].post(f'/api/jobs/interview-slots/{token}/book/',
                          {'slot_id': avail[0]['id']}, format='json')
check('créneau réservé', r.status_code == 200 and r.data.get('booked'), f"(HTTP {r.status_code})")
winner['app'].refresh_from_db()
print(f"   Entretien planifié le {winner['app'].interview_date} "
      f"({winner['app'].interview_duration} min)")

# ---------------------------------------------------------------- acceptation
step('ACCEPTATION — passage en "accepted" avec justification')
r = rh.patch(f"/api/jobs/applications/{winner['app'].pk}/update-status/",
             {'status': 'accepted',
              'reason': 'Excellents résultats aux évaluations et bon échange lors de l\'entretien.',
              'recruitment_details': 'Prise de poste le 01/12/2026, bureau Douala.',
              'expected_version': winner['app'].decision_version}, format='json')
check('candidat accepté', r.status_code == 200 and r.data.get('status') == 'accepted',
      f"(HTTP {r.status_code})")

# ---------------------------------------------------------------- contrat
step('CONTRAT — préparation PDF, envoi par email, signature OTP')
pdf = SimpleUploadedFile('contrat.pdf', b'%PDF-1.4 fake contract', content_type='application/pdf')
r = rh.post(f"/api/jobs/applications/{winner['app'].pk}/contract/prepare/",
            {'contract_file': pdf}, format='multipart')
check('contrat préparé (upload PDF)', r.status_code == 200, f"(HTTP {r.status_code})")

r = rh.post(f"/api/jobs/applications/{winner['app'].pk}/contract/send/")
check('contrat envoyé', r.status_code == 200, f"(HTTP {r.status_code})")
print(f"   Email envoyé à {mail.outbox[-1].to} — {mail.outbox[-1].subject}")

winner['app'].refresh_from_db()
token = winner['app'].contract_token
print(f"   Lien public : /api/jobs/contract/{token[:12]}…/ (expire "
      f"{winner['app'].contract_token_expires_at:%d/%m %H:%M})")

# Candidat consulte le contrat
r = winner['client'].get(f'/api/jobs/contract/{token}/')
check('candidat consulte le contrat', r.status_code == 200
      and r.data.get('contractStatus') == 'sent', f"(HTTP {r.status_code})")

# OTP : demande du code (email capturé) puis vérification
r = winner['client'].post(f'/api/jobs/contract/{token}/request-otp/')
check('code OTP envoyé', r.status_code == 200, f"(HTTP {r.status_code})")
code = last_code()
print(f"   Code OTP reçu par email : {code}")

r = winner['client'].post(f'/api/jobs/contract/{token}/verify-otp/', {'code': code}, format='json')
check('OTP vérifié', r.status_code == 200 and r.data.get('verified'), f"(HTTP {r.status_code})")

signed = SimpleUploadedFile('contrat_signe.pdf', b'%PDF-1.4 signed contract',
                            content_type='application/pdf')
r = winner['client'].post(f'/api/jobs/contract/{token}/upload-signed/',
                          {'signed_contract_file': signed}, format='multipart')
check('contrat signé déposé', r.status_code == 200 and r.data.get('status') == 'signed',
      f"(HTTP {r.status_code})")

winner['app'].refresh_from_db()
check('statut contrat = signed', winner['app'].contract_status == 'signed')
print(f"   Signé le : {winner['app'].contract_signed_at:%d/%m/%Y %H:%M}")

# ---------------------------------------------------------------- bilan
step('BILAN')
from apps.jobs.models import AgentEvent, OnboardingPlan, RecruitmentDecisionEvent
print(f"   Candidatures : {JobApplication.objects.filter(job_offer=offer).count()}")
for c in candidates:
    c['app'].refresh_from_db()
    print(f"   - {c['app'].applicant_name:<22} statut={c['app'].status:<11} "
          f"contrat={c['app'].contract_status}")
print(f"   Événements de décision : {RecruitmentDecisionEvent.objects.filter(application__job_offer=offer).count()}")
print(f"   Événements agent (audit) : {AgentEvent.objects.filter(target_id__in=[str(a.pk) for a in [c['app'] for c in candidates]]).count()}")
plan = getattr(winner['app'], 'onboarding_plan', None)
print(f"   Plan d'onboarding créé : {'oui' if plan else 'non'}")
print(f"   Emails capturés : {len(mail.outbox)}")

print('\n' + '=' * 70)
print(f'RESULTAT : {len(PASS)} OK, {len(FAIL)} KO')
if FAIL:
    print('Échecs :', FAIL)
print('=' * 70)
