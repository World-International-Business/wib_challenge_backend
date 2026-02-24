from io import BytesIO

import pymupdf
from PIL import Image
from google.genai import types
from google.genai.types import GenerateContentConfigDict
from pydantic import BaseModel

from typing import Optional

from django.conf import settings
from django.utils import timezone

from apps.jobs.models import JobOffer, JobApplication, JobApplicationAnalysis
from apps.candidates.models import CandidateProfile
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
    user = getattr(job_application, 'user', None)
    profile = getattr(user, 'profile', None) if user else None

    if not resume or not getattr(resume, 'name', None):
        # Aucun fichier CV : tenter d'utiliser le profil candidat comme "CV texte"
        if isinstance(profile, CandidateProfile):
            response = analyze_profile(job_application, job_offer, profile, fiche_poste_text)
        else:
            # Aucun profil exploitable non plus : on retourne une erreur locale
            job_application.ai_analysis = "Aucun CV ou profil détaillé fourni : analyse impossible."
            job_application.ai_decision = False

            analysis.status = JobApplicationAnalysis.Status.FAILED
            analysis.provider = JobApplicationAnalysis.Provider.LOCAL
            analysis.analysis_markdown = job_application.ai_analysis
            analysis.decision = job_application.ai_decision
            analysis.error = "no_resume_or_profile"
            analysis.finished_at = timezone.now()

            if save:
                job_application.save()
                analysis.save()
            return job_application
    else:
        pdf_path = resume.path
        response = analyze_cv_pdf(pdf_path, fiche_poste_text)

    # Fallback local si Gemini a échoué et que l'option est activée
    if (
        getattr(settings, 'LOCAL_MATCHING_FALLBACK', False)
        and isinstance(response.analyse, str)
        and response.analyse.startswith("Erreur durant l'analyse Gemini")
    ):
        try:
            # Déterminer la source de texte à utiliser
            if resume and getattr(resume, 'name', None):
                # Re-extraire le texte du CV PDF
                cv_text, _ = extract_text_native(resume.path)
                text_source = cv_text or ""
            elif isinstance(profile, CandidateProfile):
                text_source = _build_profile_text(profile)
            else:
                text_source = ""

            text_lower = text_source.lower()
            candidate_skills: list[str] = []
            for skill_name in job_offer.skills.values_list('name', flat=True):
                if not skill_name:
                    continue
                name_str = str(skill_name).strip()
                if not name_str:
                    continue
                if name_str.lower() in text_lower:
                    candidate_skills.append(name_str)

            # Mettre à jour la réponse pour réutiliser le pipeline existant
            if candidate_skills:
                response.skills = candidate_skills
                response.accept = True
                response.analyse = (
                    "Analyse locale (fallback) basée sur les mots-clés de compétences détectés dans le CV/profil."
                )
            else:
                # Aucun mot-clé trouvé : on garde la décision négative mais clarifie le message
                response.skills = []
                response.accept = False
                response.analyse = (
                    "Gemini indisponible et aucun mot-clé de compétence requis détecté dans le CV/profil."
                )
        except Exception as _:
            # En cas d'erreur dans le fallback, on garde la réponse initiale
            pass

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


def _build_profile_text(profile: CandidateProfile) -> str:
    """Construit un texte de type CV à partir du CandidateProfile et de ses relations.

    Ce texte sera utilisé comme alternative lorsqu'aucun fichier CV n'est disponible.
    """
    lines: list[str] = []

    user = profile.user
    full_name = user.get_full_name() or user.email
    lines.append(f"Nom complet: {full_name}")
    if profile.profession:
        lines.append(f"Profession: {profile.profession.title}")
    if profile.location:
        lines.append(f"Localisation: {profile.location}")
    if profile.short_bio:
        lines.append(f"Résumé: {profile.short_bio}")
    if profile.biography:
        lines.append(f"Biographie: {profile.biography}")
    if profile.years_experience is not None:
        lines.append(f"Années d'expérience: {profile.years_experience}")
    if profile.highest_degree is not None:
        lines.append(f"Diplôme le plus élevé (Bac+): {profile.highest_degree}")

    # Technologies
    techs = []
    for pt in profile.profile_technologies.select_related('technology').all():
        techs.append(f"{pt.technology.name} (niveau {pt.level})")
    if techs:
        lines.append("Compétences techniques: " + ", ".join(techs))

    # Langues
    langs = []
    for lang in profile.languages.all():
        langs.append(f"{lang.name} (niveau {lang.level})")
    if langs:
        lines.append("Langues: " + ", ".join(langs))

    # Expériences
    experiences = []
    for exp in profile.experiences.all():
        exp_str = f"{exp.title} chez {exp.company} à {exp.location} du {exp.start_date}"
        if exp.end_date:
            exp_str += f" au {exp.end_date}"
        if exp.still_working:
            exp_str += " (poste actuel)"
        if exp.description:
            exp_str += f". Description: {exp.description}"
        experiences.append(exp_str)
    if experiences:
        lines.append("Expériences professionnelles:\n- " + "\n- ".join(experiences))

    # Formations
    educations = []
    for edu in profile.educations.all():
        edu_str = f"{edu.diploma} en {edu.speciality or ''} à {edu.name} (année {edu.year_of_graduation})"
        educations.append(edu_str)
    if educations:
        lines.append("Formations:\n- " + "\n- ".join(educations))

    # Projets
    projects = []
    for proj in profile.projects.all():
        proj_str = f"{proj.name} (début: {proj.start_date})"
        if proj.description:
            proj_str += f". Description: {proj.description}"
        if proj.link:
            proj_str += f". Lien: {proj.link}"
        projects.append(proj_str)
    if projects:
        lines.append("Projets:\n- " + "\n- ".join(projects))

    return "\n".join(lines)


def analyze_profile(job_application: JobApplication, job_offer: JobOffer, profile: CandidateProfile, fiche_poste_text: str) -> Response:
    """Analyse une candidature à partir du profil candidat (sans fichier CV).

    On envoie à Gemini un texte construit à partir du profil + la fiche de poste.
    """
    profile_text = _build_profile_text(profile)

    prompt = f"""
Tu es un recruteur expert.

Tu vas recevoir le profil détaillé d'un candidat (informations structurées, expériences, compétences)
ainsi qu'une fiche de poste en texte.

1) Donne une analyse détaillée en markdown du profil vis-à-vis de cette fiche de poste.
2) Extrait des informations structurées du candidat.

Fiche de poste :
{fiche_poste_text}
"""

    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                profile_text,
                prompt,
            ],
            config=GenerateContentConfigDict(
                response_schema=Response,
                response_mime_type='application/json'
            ),
        )
        return response.parsed
    except Exception as e:
        print("❌ Erreur Gemini (profil) :", e)
        return Response(
            analyse="Erreur durant l'analyse Gemini à partir du profil.",
            accept=False,
        )

