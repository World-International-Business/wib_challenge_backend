# -*- coding: utf-8 -*-
"""Simulation pipeline post-publication rattachée à l'organisation Z-TECH.

Les candidatures apparaîtront dans le dashboard du compte yvanmoko6@gmail.com.
Lancer :  env\\Scripts\\python.exe manage.py shell < simulate_ztech.py
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
from apps.evaluations.models import Evaluation, Submission, SubmissionAttempt
from apps.jobs.models import JobApplication, JobApplicationEvaluation, JobCategory, JobOffer
from apps.organizations.models import Organization
from apps.questions.models import Question
from services.offer_distribution import publish_offer

PASS, FAIL = [], []


def step(t):
    print('\n' + '=' * 70 + f'\n>> {t}\n' + '=' * 70)


def check(label, ok, extra=''):
    (PASS if ok else FAIL).append(label)
    print(f"   [{'OK' if ok else 'KO'}] {label} {extra}")


def api(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


def last_code():
    m = re.search(r'(\d{6})', mail.outbox[-1].body)
    return m.group(1) if m else None


# ---------------------------------------------------------------- setup
step('SETUP — réutilisation de Z-TECH (yvanmoko6@gmail.com)')

org = Organization.objects.get(name='Z-TECH')
recruiter = org.account
print(f"   Org : {org.name} (id={org.pk}) | Recruteur : {recruiter.email}")

suffix = uuid.uuid4().hex[:6]
category, _ = JobCategory.objects.get_or_create(title='Ingénieur Logiciel')

evals = {}
for etype, title in (('technical', 'Test technique Python/Django'),
                     ('psychotech', 'Test psychotechnique'),
                     ('personality', 'Test de personnalité')):
    ev = Evaluation.objects.create(
        title=f'{title} ZTECH-{suffix}', publisher=recruiter,
        evaluation_type=etype, is_active=True, archived=False,
        difficulty='intermediate')
    q = Question.objects.create(
        title=f'Question {etype}', explanation='explication',
        difficulty='medium', status=Question.Status.PUBLISHED,
        publisher=recruiter, weight=100)
    ev.questions.add(q)
    evals[etype] = ev

offer = JobOffer.objects.create(
    title=f'Ingénieur Backend Python (simulation {suffix})', company=org, poste=category,
    description='Concevoir et maintenir les APIs backend du produit.',
    responsibilities='Développement Django/DRF, CI/CD, revues de code.',
    requirements='3+ ans Python/Django, PostgreSQL, Docker.',
    benefits='Mutuelle, télétravail partiel, budget formation.',
    salary='450000-650000', currency='XAF', job_type='cdi',
    experience_level='senior', location='Douala', remote_allowed=True,
    required_documents=['cv', 'cover_letter'],
    status=JobOffer.Status.DRAFT,
    technical_evaluation=evals['technical'],
    psychotech_evaluation=evals['psychotech'],
    personality_evaluation=evals['personality'])

step('PUBLICATION — publish_offer()')
pub = publish_offer(offer)
for ch in pub['channels']:
    print(f"   canal {ch['name']:<14} -> {ch['state']} {ch.get('error') or ''}")
check('offre publiée', offer.status == 'published')

# ---------------------------------------------------------------- candidats
step('CANDIDATURES — 4 candidats postulent (1 restera pending)')
candidates = []
persons = [
    ('Junior', 'EnAttente', 40),    # restera pending
    ('Junior', 'Faible', 30),       # rejeté
    ('Awa', 'Candidate', 85),       # shortlistée puis shortlist
    ('Marc', 'Excellent', 92),      # shortlisté puis accepté + contrat
]
for i, (first, last, score) in enumerate(persons, 1):
    u = User.objects.create_user(
        email=f'ztech.cand{i}.{suffix}@sim.local', password='cand-pass',
        first_name=first, last_name=last, role=User.Roles.USER)
    c = api(u)
    cv = SimpleUploadedFile(f'cv_{first}.pdf', b'%PDF-1.4 fake cv', content_type='application/pdf')
    r = c.post(f'/api/jobs/offers/{offer.pk}/apply/',
               {'applicant_name': f'{first} {last}',
                'applicant_email': u.email,
                'cover_letter': f'Motivation {first} {last} pour le poste.',
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
print(f"   Statistiques : {r.data.get('statistics')}")

# ---------------------------------------------------------------- présélection
step('PRÉSÉLECTION')
for c in candidates:
    if c['app'].applicant_name.startswith('Junior EnAttente'):
        continue  # reste pending exprès
    target = 'shortlisted' if c['score'] >= 50 else 'rejected'
    r = rh.patch(f"/api/jobs/applications/{c['app'].pk}/update-status/",
                 {'status': target, 'reason': 'Décision RH simulée',
                  'expected_version': c['app'].decision_version}, format='json')
    check(f"{c['app'].applicant_name} -> {target}",
          r.status_code == 200 and r.data.get('status') == target, f"(HTTP {r.status_code})")
    c['app'].refresh_from_db()

# ---------------------------------------------------------------- évaluations
step('ÉVALUATIONS — assignation + passage des tests')
shortlisted = [c for c in candidates if c['app'].status == 'shortlisted']
for c in shortlisted:
    r = rh.post(f"/api/jobs/applications/{c['app'].pk}/assign-evaluations/")
    check(f"évaluations assignées à {c['app'].applicant_name}", r.status_code == 200,
          f"(HTTP {r.status_code})")
    for jae in JobApplicationEvaluation.objects.filter(job_application=c['app']):
        attempt = SubmissionAttempt.objects.filter(
            evaluation=jae.evaluation,
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

# ---------------------------------------------------------------- entretien
step('ENTRETIEN — booking public par le meilleur candidat')
winner = max(shortlisted, key=lambda c: c['score'])
slots = [
    {'starts_at': (timezone.now() + timedelta(days=2, hours=9)).isoformat(),
     'ends_at': (timezone.now() + timedelta(days=2, hours=10)).isoformat()},
    {'starts_at': (timezone.now() + timedelta(days=3, hours=14)).isoformat(),
     'ends_at': (timezone.now() + timedelta(days=3, hours=15)).isoformat()},
]
r = rh.post(f"/api/jobs/applications/{winner['app'].pk}/interview-booking/", {'slots': slots}, format='json')
check('créneaux créés', r.status_code == 201, f"(HTTP {r.status_code})")
token = r.data['token']
r = winner['client'].get(f'/api/jobs/interview-slots/{token}/')
avail = r.data.get('slots', [])
check('créneaux visibles', r.status_code == 200 and len(avail) == 2)
r = winner['client'].post(f'/api/jobs/interview-slots/{token}/book/',
                          {'slot_id': avail[0]['id']}, format='json')
check('créneau réservé', r.status_code == 200 and r.data.get('booked'), f"(HTTP {r.status_code})")
winner['app'].refresh_from_db()
print(f"   Entretien : {winner['app'].interview_date} ({winner['app'].interview_duration} min)")

# ---------------------------------------------------------------- acceptation
step('ACCEPTATION')
r = rh.patch(f"/api/jobs/applications/{winner['app'].pk}/update-status/",
             {'status': 'accepted',
              'reason': 'Excellents scores aux évaluations et bon entretien.',
              'recruitment_details': 'Prise de poste le 01/12/2026, bureau Douala.',
              'expected_version': winner['app'].decision_version}, format='json')
check('candidat accepté', r.status_code == 200 and r.data.get('status') == 'accepted',
      f"(HTTP {r.status_code})")

# ---------------------------------------------------------------- contrat
step('CONTRAT — prepare / send / OTP / signature')
pdf = SimpleUploadedFile('contrat.pdf', b'%PDF-1.4 fake contract', content_type='application/pdf')
r = rh.post(f"/api/jobs/applications/{winner['app'].pk}/contract/prepare/",
            {'contract_file': pdf}, format='multipart')
check('contrat préparé', r.status_code == 200, f"(HTTP {r.status_code})")
r = rh.post(f"/api/jobs/applications/{winner['app'].pk}/contract/send/")
check('contrat envoyé', r.status_code == 200, f"(HTTP {r.status_code})")
winner['app'].refresh_from_db()
token = winner['app'].contract_token
print(f"   Lien : /api/jobs/contract/{token[:12]}…/ → {winner['app'].applicant_email}")

r = winner['client'].get(f'/api/jobs/contract/{token}/')
check('consultation contrat', r.status_code == 200 and r.data.get('contractStatus') == 'sent')
r = winner['client'].post(f'/api/jobs/contract/{token}/request-otp/')
check('OTP envoyé', r.status_code == 200, f"(HTTP {r.status_code})")
code = last_code()
print(f"   Code OTP : {code}")
r = winner['client'].post(f'/api/jobs/contract/{token}/verify-otp/', {'code': code}, format='json')
check('OTP vérifié', r.status_code == 200 and r.data.get('verified'), f"(HTTP {r.status_code})")
signed = SimpleUploadedFile('signe.pdf', b'%PDF-1.4 signed', content_type='application/pdf')
r = winner['client'].post(f'/api/jobs/contract/{token}/upload-signed/',
                          {'signed_contract_file': signed}, format='multipart')
check('contrat signé', r.status_code == 200 and r.data.get('status') == 'signed', f"(HTTP {r.status_code})")
winner['app'].refresh_from_db()
check('contract_status=signed', winner['app'].contract_status == 'signed')

# ---------------------------------------------------------------- bilan
step('BILAN — visible dans ton dashboard Z-TECH')
print(f"   Offre : {offer.title} (id={offer.pk}, status={offer.status})")
for c in candidates:
    c['app'].refresh_from_db()
    print(f"   - {c['app'].applicant_name:<18} statut={c['app'].status:<11} "
          f"contrat={c['app'].contract_status}")
print(f"   Emails capturés : {len(mail.outbox)}")
print('\n' + '=' * 70)
print(f'RESULTAT : {len(PASS)} OK, {len(FAIL)} KO' + (f' — échecs: {FAIL}' if FAIL else ''))
print('=' * 70)
