from django.core.management import BaseCommand

from apps.evaluations.models import Profession
from apps.jobs.models import JobCategory


# Catalogue de métiers par secteur — utilisé comme liste des `poste` (JobCategory)
# pour le formulaire manuel et le matching de l'agent Wiba.
JOB_TITLES = {
    'Informatique / Tech': [
        'Développeur Web', 'Développeur Full Stack', 'Développeur Frontend', 'Développeur Backend',
        'Développeur Mobile', 'Développeur Android', 'Développeur iOS', 'Développeur Python',
        'Développeur Java', 'Développeur JavaScript', 'Développeur PHP', 'Développeur .NET',
        'Développeur C++', 'Développeur Embarqué', 'Ingénieur Logiciel', 'DevOps',
        'Administrateur Système', 'Administrateur Réseau', 'Administrateur de base de données',
        'Architecte Cloud', 'Architecte Logiciel', 'Ingénieur Cloud', 'Ingénieur Sécurité',
        'Analyste Cybersécurité', 'Pentester', 'Data Scientist', 'Data Analyst',
        'Data Engineer', 'Ingénieur Machine Learning', 'Ingénieur IA', 'Analyste BI',
        'Chef de projet IT', 'Product Owner', 'Scrum Master', 'Product Manager',
        'UX Designer', 'UI Designer', 'Testeur QA', 'Ingénieur QA', 'Support IT',
        'Technicien informatique', 'Consultant IT', 'CTO', 'Webmaster', 'Intégrateur Web',
        'Ingénieur Blockchain', 'Administrateur Salesforce', 'Consultant ERP',
    ],
    'Vente / Commerce': [
        'Commercial', 'Commercial terrain', 'Commercial B2B', 'Commercial B2C',
        'Télévendeur', 'Téléconseiller', 'Conseiller commercial', 'Responsable commercial',
        'Directeur commercial', 'Business Developer', 'Account Manager', 'Key Account Manager',
        'Vendeur en magasin', 'Vendeuse en magasin', 'Caissier', 'Hôte de caisse',
        'Responsable de magasin', 'Chef de rayon', 'Merchandiser', 'Négociateur immobilier',
        'Agent commercial', 'Attaché commercial', 'Ingénieur commercial', 'Commercial export',
        'Acheteur', 'Category Manager', 'Responsable e-commerce', 'Chargé de clientèle',
    ],
    'Marketing / Communication': [
        'Responsable marketing', 'Chef de produit', 'Chargé de communication', 'Community Manager',
        'Social Media Manager', 'Traffic Manager', 'SEO Manager', 'Content Manager',
        'Rédacteur web', 'Copywriter', 'Graphiste', 'Directeur artistique', 'Brand Manager',
        'Growth Hacker', 'CRM Campaign Manager', 'Chargé d\'études marketing', 'Attaché de presse',
        'Responsable événementiel', 'Media Planner', 'Motion Designer',
    ],
    'Ressources Humaines': [
        'Chargé RH', 'Assistant RH', 'Responsable RH', 'DRH', 'Recruteur',
        'Chargé de recrutement', 'Gestionnaire de paie', 'Chargé de formation',
        'Talent Acquisition Specialist', 'HR Business Partner', 'Office Manager',
    ],
    'Finance / Comptabilité / Banque': [
        'Comptable', 'Aide-comptable', 'Comptable général', 'Chef comptable', 'Expert-comptable',
        'Auditeur', 'Contrôleur de gestion', 'Analyste financier', 'Trésorier', 'DAF',
        'Conseiller bancaire', 'Chargé d\'affaires banque', 'Gestionnaire back-office',
        'Analyste crédit', 'Agent de crédit', 'Actuaire', 'Trader', 'Gestionnaire de patrimoine',
        'Fiscaliste', 'Commissaire aux comptes', 'Caissier banque',
    ],
    'Assurance': [
        'Conseiller en assurance', 'Agent général d\'assurance', 'Courtier en assurance',
        'Gestionnaire sinistres', 'Souscripteur assurance', 'Expert d\'assuré',
    ],
    'Santé': [
        'Médecin', 'Médecin généraliste', 'Chirurgien', 'Pédiatre', 'Gynécologue', 'Dentiste',
        'Infirmier', 'Infirmière', 'Sage-femme', 'Pharmacien', 'Assistant pharmacien',
        'Aide-soignant', 'Kinésithérapeute', 'Opticien', 'Psychologue', 'Psychiatre',
        'Radiologue', 'Technicien de laboratoire', 'Ambulancier', 'Diététicien',
        'Ergothérapeute', 'Orthophoniste', 'Vétérinaire', 'Assistant dentaire',
        'Visiteur médical', 'Délégué pharmaceutique',
    ],
    'Éducation / Formation': [
        'Enseignant', 'Professeur des écoles', 'Instituteur', 'Professeur de lycée',
        'Professeur d\'université', 'Formateur', 'Éducateur', 'Surveillant scolaire',
        'Conseiller d\'orientation', 'Directeur d\'école', 'Documentaliste', 'Tuteur',
    ],
    'BTP / Construction': [
        'Maçon', 'Chef de chantier', 'Conducteur de travaux', 'Architecte',
        'Ingénieur BTP', 'Ingénieur génie civil', 'Électricien bâtiment', 'Plombier',
        'Charpentier', 'Menuisier', 'Peintre en bâtiment', 'Carreleur', 'Soudeur',
        'Géomètre-topographe', 'Dessinateur-projeteur', 'Grutier', 'Conducteur d\'engins',
        'Métreur', 'Coordinateur SPS', 'Étanchéiste', 'Plâtrier',
    ],
    'Industrie / Production': [
        'Opérateur de production', 'Chef d\'équipe production', 'Technicien de maintenance',
        'Ingénieur de production', 'Ingénieur qualité', 'Contrôleur qualité', 'Magasinier',
        'Technicien méthodes', 'Mécanicien industriel', 'Électromécanicien', 'Automaticien',
        'Opérateur CNC', 'Fraiseur', 'Tourneur', 'Chaudronnier', 'Responsable production',
        'Ingénieur HSE', 'Technicien HSE', 'Directeur d\'usine', 'Ordonnanceur',
    ],
    'Logistique / Transport': [
        'Chauffeur', 'Chauffeur poids lourd', 'Chauffeur-livreur', 'Livreur', 'Coursier',
        'Responsable logistique', 'Agent logistique', 'Gestionnaire de stock', 'Cariste',
        'Préparateur de commandes', 'Affréteur', 'Transit agent', 'Agent de transit',
        'Supply Chain Manager', 'Déménageur', 'Receveur', 'Dispatch rider',
    ],
    'Hôtellerie / Restauration / Tourisme': [
        'Serveur', 'Serveuse', 'Cuisinier', 'Chef cuisinier', 'Commis de cuisine', 'Pâtissier',
        'Boulanger', 'Barman', 'Réceptionniste d\'hôtel', 'Femme de chambre', 'Voiturier',
        'Responsable de restaurant', 'Maître d\'hôtel', 'Agent de voyage', 'Guide touristique',
        'Chef de rang', 'Sommelier', 'Concierge',
    ],
    'Juridique': [
        'Avocat', 'Juriste', 'Notaire', 'Huissier de justice', 'Paralégal', 'Magistrat',
        'Greffier', 'Conseil juridique', 'Juriste d\'entreprise', 'Secrétaire juridique',
        'Commissaire-priseur',
    ],
    'Administration / Secrétariat': [
        'Assistant administratif', 'Assistante de direction', 'Secrétaire', 'Standardiste',
        'Agent administratif', 'Gestionnaire administratif', 'Hôte/Hôtesse d\'accueil',
        'Data Entry', 'Archiviste', 'Adjoint administratif', 'Responsable administratif',
    ],
    'Agriculture / Élevage / Pêche': [
        'Agriculteur', 'Exploitant agricole', 'Ouvrier agricole', 'Éleveur', 'Agronome',
        'Ingénieur agronome', 'Pisciculteur', 'Pêcheur', 'Jardinier', 'Pépiniériste',
        'Technicien agricole', 'Maraîcher', 'Viticulteur', 'Apiculteur',
    ],
    'Sécurité': [
        'Agent de sécurité', 'Agent de surveillance', 'Garde du corps', 'Vigile',
        'Opérateur vidéosurveillance', 'Pompier', 'Policier', 'Gendarme',
        'Responsable sécurité', 'Convoyeur de fonds',
    ],
    'Automobile / Mécanique': [
        'Mécanicien automobile', 'Électricien automobile', 'Carrossier', 'Peintre carrosserie',
        'Conseiller technique automobile', 'Contrôleur technique', 'Dépanneur automobile',
    ],
    'Immobilier': [
        'Agent immobilier', 'Gestionnaire de biens', 'Syndic de copropriété',
        'Promoteur immobilier', 'Expert immobilier', 'Gardien d\'immeuble', 'Concierge immobilier',
    ],
    'Art / Culture / Médias': [
        'Journaliste', 'Rédacteur en chef', 'Photographe', 'Vidéaste', 'Monteur vidéo',
        'Réalisateur', 'Animateur radio/TV', 'Musicien', 'Chanteur', 'Comédien', 'Acteur',
        'Designer', 'Illustrateur', 'Auteur', 'Écrivain', 'Correcteur', 'Traducteur',
        'Interprète', 'Bibliothécaire', 'Conservateur de musée', 'DJ', 'Sound designer',
    ],
    'Beauté / Bien-être / Sport': [
        'Coiffeur', 'Coiffeuse', 'Esthéticienne', 'Maquilleuse', 'Manucure', 'Barbier',
        'Masseur', 'Coach sportif', 'Coach personnel', 'Educateur sportif', 'Animateur sportif',
    ],
    'Sciences / Recherche': [
        'Chercheur', 'Ingénieur R&D', 'Technicien de recherche', 'Biologiste', 'Chimiste',
        'Physicien', 'Statisticien', 'Géologue', 'Ingénieur environnement',
    ],
    'Social / ONG': [
        'Travailleur social', 'Éducateur spécialisé', 'Animateur social', 'Assistant social',
        'Chargé de projet ONG', 'Coordinateur humanitaire', 'Fundraiser',
        'Médiateur social', 'Conseiller en insertion',
    ],
    'Nettoyage / Services': [
        'Agent d\'entretien', 'Agent de nettoyage', 'Femme de ménage', 'Homme de ménage',
        'Agent de blanchisserie', 'Employé de maison', 'Nounou', 'Auxiliaire de vie',
    ],
    'Direction / Management': [
        'Directeur général', 'Directeur', 'CEO', 'COO', 'CFO', 'Directeur des opérations',
        'Directeur de site', 'Directeur de projet', 'Chef de projet', 'Team Leader',
        'Manager', 'Superviseur', 'Cadre de santé',
    ],
    'Énergie / Environnement': [
        'Ingénieur énergie', 'Technicien énergie', 'Installateur panneaux solaires',
        'Technicien traitement des eaux', 'Agent de collecte', 'Éboueur',
        'Chargé environnement', 'Ingénieur environnement',
    ],
    'Artisanat / Métiers manuels': [
        'Tailleur', 'Couturière', 'Cordonnier', 'Bijoutier', 'Ébéniste', 'Forgeron',
        'Imprimeur', 'Sérigraphe', 'Relieur', 'Vitrier', 'Ferronnier', 'Tapissier',
    ],
}


class Command(BaseCommand):
    help = 'Charge le catalogue de métiers (JobCategory) : liste intégrée + titres des Profession existantes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Affiche le nombre de titres sans écrire.')

    def handle(self, *args, **options):
        titles = {title for sector_titles in JOB_TITLES.values() for title in sector_titles}
        # Les professions utilisées par les évaluations partagent le même vocabulaire de postes.
        titles.update(
            title.strip() for title in Profession.objects.values_list('title', flat=True)
            if title and title.strip() and title.strip().lower() != 'autre'
        )
        self.stdout.write(f'{len(titles)} titres à charger.')
        if options['dry_run']:
            return
        created = 0
        for title in sorted(titles, key=str.lower):
            _, was_created = JobCategory.objects.get_or_create(title=title[:100])
            created += was_created
        self.stdout.write(self.style.SUCCESS(
            f'{created} catégories créées, {JobCategory.objects.count()} au total.'))
