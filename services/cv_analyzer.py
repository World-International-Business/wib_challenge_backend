from io import BytesIO

import pymupdf
from PIL import Image
from google.genai import types
from google.genai.types import GenerateContentConfigDict
from pydantic import BaseModel

from typing import Optional

from django.utils import timezone

from apps.jobs.models import JobOffer, JobApplication, JobApplicationAnalysis
from services.utils import get_genai_client


class Response(BaseModel):
    analyse: str
    accept: bool
    skills: list[str] = []
    years_experience: Optional[int] = None
    location: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None


def extract_text_native(pdf_path):
    texte_final = ""
    images: list[Image.Image] = []
    doc = pymupdf.open(pdf_path)

    for page_num, page in enumerate(doc.pages()):
        text = page.get_text().strip()
        print(text)
        if text:
            texte_final += f"\n\n### Page {page_num + 1} (texte détecté)\n{text}"
        else:
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)

    return texte_final.strip(), images


def png(image):
    io = BytesIO()
    image.save(io, format='PNG')
    return io.getvalue()


def analyze_job_application(job_application: JobApplication, job_offer: JobOffer, save=True) -> JobApplication:
    # Construire le résumé de la fiche de poste
    fiche_poste_text = f"""
**Titre**: {job_offer.title}
**Description**: {job_offer.description}
**Responsabilités**: {job_offer.responsibilities}
**Prérequis**: {job_offer.requirements}
**Avantages**: {job_offer.benefits}
**Salaire**: {job_offer.salary} {job_offer.currency}
**Type de contrat**: {job_offer.get_job_type_display()}
**Niveau d'expérience**: {job_offer.get_experience_level_display()}
**Localisation**: {job_offer.location}
**Télétravail**: {"Oui" if job_offer.remote_allowed else "Non"}
"""

    analysis, _ = JobApplicationAnalysis.objects.get_or_create(application=job_application)
    analysis.status = JobApplicationAnalysis.Status.PROCESSING
    analysis.started_at = timezone.now()
    analysis.error = ""
    if save:
        analysis.save()

    resume = getattr(job_application, 'resume', None)
    if not resume or not getattr(resume, 'name', None):
        job_application.ai_analysis = "Aucun CV fourni: analyse impossible."
        job_application.ai_decision = False

        analysis.status = JobApplicationAnalysis.Status.FAILED
        analysis.provider = JobApplicationAnalysis.Provider.LOCAL
        analysis.analysis_markdown = job_application.ai_analysis
        analysis.decision = job_application.ai_decision
        analysis.error = "no_resume"
        analysis.finished_at = timezone.now()

        if save:
            job_application.save()
            analysis.save()
        return job_application

    pdf_path = resume.path
    response = analyze_cv_pdf(pdf_path, fiche_poste_text)

    job_application.ai_analysis = response.analyse
    job_application.ai_decision = response.accept

    # Sauvegarder l'extraction structurée
    analysis.extracted_data = {
        'skills': response.skills or [],
        'years_experience': response.years_experience,
        'location': response.location,
        'full_name': response.full_name,
        'email': response.email,
    }

    # Calculer un score simple basé sur les compétences requises de l'offre
    required_skills = list(job_offer.skills.values_list('name', flat=True))
    required_set = {s.strip().lower() for s in required_skills if s}
    candidate_set = {s.strip().lower() for s in (response.skills or []) if s}

    if required_set:
        matched = required_set.intersection(candidate_set)
        score = round(len(matched) * 100 / max(len(required_set), 1))
    else:
        score = 100 if response.accept else 0

    job_application.match_score = max(0, min(100, int(score)))
    job_application.is_matched = bool(job_application.match_score >= 70 or response.accept)

    analysis.status = JobApplicationAnalysis.Status.DONE
    analysis.provider = JobApplicationAnalysis.Provider.GEMINI
    analysis.analysis_markdown = response.analyse
    analysis.decision = response.accept
    analysis.finished_at = timezone.now()

    if save:
        job_application.save()
        analysis.save()

    return job_application


def analyze_cv_pdf(pdf_path, fiche_poste_text) -> Response:
    cv_text, cv_page_images = extract_text_native(pdf_path)

    prompt = f"""
Tu es un recruteur expert.

Tu vas recevoir un CV sous forme d'images (pages PDF) + une fiche de poste en texte.

1) Donne une analyse détaillée en markdown du CV vis-à-vis de cette fiche de poste.
2) Extrait des informations structurées du candidat.

Fiche de poste :
{fiche_poste_text}
"""

    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                *[types.Part.from_bytes(data=png(image), mime_type='image/png') for image in cv_page_images],
                cv_text,
                prompt
            ],
            config=GenerateContentConfigDict(
                response_schema=Response,
                response_mime_type='application/json'
            )
        )
        return response.parsed

    except Exception as e:
        print("❌ Erreur Gemini :", e)
        return Response(
            analyse="Erreur durant l'analyse Gemini.",
            accept=False
        )
