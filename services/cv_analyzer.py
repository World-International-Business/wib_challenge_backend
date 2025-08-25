from io import BytesIO

import pymupdf
from PIL import Image
from google.genai import types
from google.genai.types import GenerateContentConfigDict
from pydantic import BaseModel

from apps.jobs.models import JobOffer, JobApplication
from services.utils import get_genai_client


class Response(BaseModel):
    analyse: str
    accept: bool


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
**Salaire**: {job_offer.salary_min} - {job_offer.salary_max} {job_offer.currency}
**Type de contrat**: {job_offer.get_job_type_display()}
**Niveau d'expérience**: {job_offer.get_experience_level_display()}
**Localisation**: {job_offer.location}
**Télétravail**: {"Oui" if job_offer.remote_allowed else "Non"}
"""

    pdf_path = job_application.resume.path
    response = analyze_cv_pdf(pdf_path, fiche_poste_text)

    job_application.ai_analysis = response.analyse
    job_application.ai_decision = response.accept

    if save:
        job_application.save()

    return job_application


def analyze_cv_pdf(pdf_path, fiche_poste_text) -> Response:
    cv_text, cv_page_images = extract_text_native(pdf_path)

    prompt = f"""
Tu es un recruteur expert.

Tu vas recevoir un CV sous forme d'images (pages PDF) + une fiche de poste en texte.

Donne une analyse détaillée et structuré au format markdown du ce CV vis-à-vis de cette fiche de poste :
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
