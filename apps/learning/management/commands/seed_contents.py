"""Seed automatique des contenus et quiz pour tous les modules existants en base.

Pour chaque module sans contenus, crée :
- 1 lesson markdown (cours théorique)
- 1 lesson vidéo (URL placeholder à remplacer via l'admin)
- 1 lesson ressource externe (URL placeholder)

Pour chaque module sans quiz, crée :
- 1 quiz avec 15-20 questions et 4 choix par question

Usage :
    python manage.py seed_contents          # idempotent (skip si déjà peuplé)
    python manage.py seed_contents --force  # recrée tout
"""
from django.core.management import BaseCommand
from django.db import transaction

from apps.learning.models import Module, Content, Quiz, QuizQuestion, QuizChoice
from apps.learning.management.commands.seed_data import MODULE_DATA


class Command(BaseCommand):
    help = 'Seed automatique des contenus (lessons) et quiz pour tous les modules existants'

    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Recrée les contenus et quiz même s\'ils existent déjà')

    @transaction.atomic
    def handle(self, *args, **options):
        force = options.get('force', False)

        modules = Module.objects.all().select_related('course')
        if not modules.exists():
            self.stdout.write(self.style.WARNING('Aucun module trouvé en base. Lancez seed_courses d\'abord.'))
            return

        self.stdout.write(f'Trouvé {modules.count()} modules à traiter.')

        created_contents = 0
        created_quizzes = 0
        created_questions = 0
        created_choices = 0
        skipped = 0

        for module in modules:
            module_data = MODULE_DATA.get(module.title)

            if not module_data:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ Module "{module.title}" (cours: {module.course.title}) '
                        f'non trouvé dans le mapping — contenus génériques créés'
                    )
                )
                module_data = self._generic_data(module)

            # ─── Contenus ───
            existing_contents = module.contents.all()
            if existing_contents.exists() and not force:
                self.stdout.write(
                    f'  ✓ Module "{module.title}" — {existing_contents.count()} contenu(s) déjà existant(s), ignoré'
                )
                skipped += 1
            else:
                if force and existing_contents.exists():
                    existing_contents.delete()
                    self.stdout.write(f'  🗑 Module "{module.title}" — contenus existants supprimés (--force)')

                for content_data in module_data.get('contents', []):
                    ct = content_data['content_type']
                    if ct == 'markdown':
                        # Contenu markdown : cours théorique
                        Content.objects.create(
                            module=module,
                            title=content_data['title'],
                            content_type=ct,
                            content=content_data.get('content'),
                            duration_minutes=content_data.get('duration_minutes'),
                        )
                        created_contents += 1
                        self.stdout.write(f'  + Contenu créé : {content_data["title"]} (markdown)')
                    elif ct == 'video':
                        # Vidéo placeholder avec URL placeholder
                        # L'utilisateur remplacera l'URL via l'admin
                        Content.objects.create(
                            module=module,
                            title=content_data['title'],
                            content_type=ct,
                            resource_url=content_data.get('resource_url', 'https://placeholder.com/video-pending'),
                            duration_minutes=content_data.get('duration_minutes', 30),
                        )
                        created_contents += 1
                        self.stdout.write(f'  + Vidéo placeholder : {content_data["title"]} (à remplacer via admin)')
                    elif ct == 'pdf':
                        # PDF placeholder : contourner la validation du modèle
                        # car le modèle exige un fichier pour les PDF
                        last_content = Content.objects.filter(module=module).order_by('-order').first()
                        next_order = (last_content.order + 1) if last_content else 1
                        Content.objects.bulk_create([
                            Content(
                                module=module,
                                title=content_data['title'],
                                content_type=ct,
                                content=f"# {content_data['title']}\n\n> **Placeholder** — Ajoutez le fichier PDF via l'admin Django.",
                                order=next_order,
                                duration_minutes=content_data.get('duration_minutes', 30),
                            )
                        ])
                        created_contents += 1
                        self.stdout.write(f'  + PDF placeholder : {content_data["title"]} (à remplacer via admin)')
                    elif ct == 'external':
                        # Ressource externe avec URL
                        Content.objects.create(
                            module=module,
                            title=content_data['title'],
                            content_type=ct,
                            resource_url=content_data.get('resource_url', 'https://placeholder.com/external'),
                            duration_minutes=content_data.get('duration_minutes', 20),
                        )
                        created_contents += 1
                        self.stdout.write(f'  + Ressource externe : {content_data["title"]}')

                # Ajouter un PDF placeholder automatique pour chaque module
                # L'utilisateur ajoutera le fichier PDF via l'admin Django
                has_pdf = any(c.get('content_type') == 'pdf' for c in module_data.get('contents', []))
                if not has_pdf:
                    last_content = Content.objects.filter(module=module).order_by('-order').first()
                    next_order = (last_content.order + 1) if last_content else 1
                    Content.objects.bulk_create([
                        Content(
                            module=module,
                            title=f"Document PDF : {module.title}",
                            content_type='pdf',
                            content=f"# Document PDF : {module.title}\n\n> **Placeholder** — Ajoutez le fichier PDF via l'admin Django.",
                            order=next_order,
                            duration_minutes=30,
                        )
                    ])
                    created_contents += 1
                    self.stdout.write(f'  + PDF placeholder : Document PDF : {module.title} (à remplacer via admin)')

                # Ajouter un contenu "test/exercice" en markdown
                test_content = module_data.get('test_content')
                if not test_content:
                    # Générer un test générique si non fourni
                    test_content = self._generate_test(module)
                if test_content:
                    Content.objects.create(
                        module=module,
                        title=test_content['title'],
                        content_type='markdown',
                        content=test_content['content'],
                        duration_minutes=test_content.get('duration_minutes', 30),
                    )
                    created_contents += 1
                    self.stdout.write(f'  + Test créé : {test_content["title"]}')

            # ─── Quiz ───
            has_quiz = hasattr(module, 'quiz') and module.quiz is not None
            quiz_data = module_data.get('quiz')

            if quiz_data:
                if has_quiz and not force:
                    self.stdout.write(
                        f'  ✓ Module "{module.title}" — quiz déjà existant, ignoré'
                    )
                else:
                    if has_quiz and force:
                        module.quiz.delete()

                    quiz = Quiz.objects.create(
                        module=module,
                        title=quiz_data['title'],
                        description=quiz_data.get('description', ''),
                    )
                    created_quizzes += 1
                    self.stdout.write(f'  + Quiz créé : {quiz_data["title"]}')

                    for q_data in quiz_data.get('questions', []):
                        question = QuizQuestion.objects.create(
                            quiz=quiz,
                            title=q_data['title'],
                            explanation=q_data.get('explanation', ''),
                        )
                        created_questions += 1

                        for c_data in q_data.get('choices', []):
                            QuizChoice.objects.create(
                                question=question,
                                text=c_data['text'],
                                is_correct=c_data.get('is_correct', False),
                            )
                            created_choices += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('─' * 50))
        self.stdout.write(self.style.SUCCESS(f'Résumé :'))
        self.stdout.write(self.style.SUCCESS(f'  Contenus créés  : {created_contents}'))
        self.stdout.write(self.style.SUCCESS(f'  Quiz créés      : {created_quizzes}'))
        self.stdout.write(self.style.SUCCESS(f'  Questions créées: {created_questions}'))
        self.stdout.write(self.style.SUCCESS(f'  Choix créés     : {created_choices}'))
        self.stdout.write(self.style.SUCCESS(f'  Modules ignorés : {skipped}'))
        self.stdout.write(self.style.SUCCESS('─' * 50))

    def _generate_test(self, module):
        """Génère un contenu test/exercice en markdown pour un module."""
        return {
            "title": f"Test & Exercices : {module.title}",
            "content": f"# Test & Exercices : {module.title}\n\n"
                      f"## Questions\n\n"
                      f"1. **Expliquez en vos propres mots** les concepts clés de {module.title}.\n\n"
                      f"2. **Donnez 3 exemples** concrets d'application de {module.title}.\n\n"
                      f"3. **Quelles sont les bonnes pratiques** à respecter dans ce domaine ?\n\n"
                      f"4. **Citez les outils** couramment utilisés.\n\n"
                      f"5. **Décrivez un cas d'usage** réel en entreprise.\n\n"
                      f"## Exercice pratique\n\n"
                      f"Réalisez un petit projet mettant en pratique les concepts de **{module.title}**.\n\n"
                      f"## Auto-évaluation\n\n"
                      f"- [ ] Je comprends les fondamentaux\n"
                      f"- [ ] Je peux expliquer les concepts à quelqu'un\n"
                      f"- [ ] Je peux appliquer les concepts en pratique\n"
                      f"- [ ] Je connais les bonnes pratiques",
            "duration_minutes": 30,
        }

    def _generic_data(self, module):
        """Génère des contenus génériques pour les modules non mappés."""
        return {
            "contents": [
                {
                    "title": f"Introduction : {module.title}",
                    "content_type": "markdown",
                    "content": f"# {module.title}\n\n## Introduction\n\nCe module couvre les concepts essentiels de **{module.title}** dans le cadre de la formation **{module.course.title}**.\n\n## Objectifs\n\n- Comprendre les fondamentaux\n- Mettre en pratique les concepts\n- Appliquer les bonnes pratiques\n\n## Plan du module\n\n1. Concepts théoriques\n2. Démonstration pratique\n3. Exercices et ressources",
                    "duration_minutes": 30,
                },
                {
                    "title": f"Vidéo : {module.title}",
                    "content_type": "video",
                    "resource_url": "https://placeholder.com/video-pending",
                    "duration_minutes": 40,
                },
                {
                    "title": f"Document PDF : {module.title}",
                    "content_type": "pdf",
                    "duration_minutes": 30,
                },
            ],
            "quiz": {
                "title": f"Quiz : {module.title}",
                "description": f"Testez vos connaissances sur {module.title}.",
                "questions": [
                    {
                        "title": f"Quelle est la principale compétence visée par le module '{module.title}' ?",
                        "explanation": f"Ce module vise à maîtriser les concepts de {module.title}.",
                        "choices": [
                            {"text": "Comprendre les fondamentaux", "is_correct": True},
                            {"text": "Mémoriser des dates historiques", "is_correct": False},
                            {"text": "Apprendre une langue étrangère", "is_correct": False},
                            {"text": "Pratiquer un sport", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Quelle est la meilleure approche pour apprendre efficacement ?",
                        "explanation": "La pratique régulière et la mise en situation sont les plus efficaces.",
                        "choices": [
                            {"text": "Lire uniquement la théorie", "is_correct": False},
                            {"text": "Pratiquer régulièrement", "is_correct": True},
                            {"text": "Regarder uniquement des vidéos", "is_correct": False},
                            {"text": "Ne rien faire", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Pourquoi est-il important de pratiquer ?",
                        "explanation": "La pratique permet de consolider les acquis et de découvrir des cas concrets.",
                        "choices": [
                            {"text": "Pour gagner du temps", "is_correct": False},
                            {"text": "Pour consolider les acquis", "is_correct": True},
                            {"text": "Pour éviter d'apprendre", "is_correct": False},
                            {"text": "Pour impressionner", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Quelle est la première étape pour maîtriser un sujet ?",
                        "explanation": "Comprendre les fondamentaux est la première étape.",
                        "choices": [
                            {"text": "Comprendre les fondamentaux", "is_correct": True},
                            {"text": "Mémoriser sans comprendre", "is_correct": False},
                            {"text": "Sauter les bases", "is_correct": False},
                            {"text": "Aller directement aux projets", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Que faut-il faire après avoir appris la théorie ?",
                        "explanation": "Mettre en pratique les concepts via des exercices.",
                        "choices": [
                            {"text": "Oublier la théorie", "is_correct": False},
                            {"text": "Mettre en pratique via des exercices", "is_correct": True},
                            {"text": "Ne rien faire", "is_correct": False},
                            {"text": "Lire un autre livre", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Pourquoi consulter des ressources externes ?",
                        "explanation": "Pour approfondir et avoir différentes perspectives.",
                        "choices": [
                            {"text": "Pour perdre du temps", "is_correct": False},
                            {"text": "Pour approfondir et avoir différentes perspectives", "is_correct": True},
                            {"text": "Pour éviter d'apprendre", "is_correct": False},
                            {"text": "Ce n'est pas utile", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Qu'est-ce qui aide à mieux retenir l'information ?",
                        "explanation": "La combinaison de théorie et pratique régulière.",
                        "choices": [
                            {"text": "La théorie seule", "is_correct": False},
                            {"text": "La combinaison de théorie et pratique régulière", "is_correct": True},
                            {"text": "La pratique seule", "is_correct": False},
                            {"text": "Ne rien faire", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Comment évaluer sa compréhension d'un sujet ?",
                        "explanation": "Faire des quiz et des exercices pratiques.",
                        "choices": [
                            {"text": "Faire des quiz et des exercices pratiques", "is_correct": True},
                            {"text": "Lire le cours une deuxième fois", "is_correct": False},
                            {"text": "Demander à un ami", "is_correct": False},
                            {"text": "Ne pas s'évaluer", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Que faire si on ne comprend pas un concept ?",
                        "explanation": "Chercher des ressources alternatives et demander de l'aide.",
                        "choices": [
                            {"text": "Abandonner", "is_correct": False},
                            {"text": "Chercher des ressources alternatives et demander de l'aide", "is_correct": True},
                            {"text": "Ignorer le concept", "is_correct": False},
                            {"text": "Mémoriser sans comprendre", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Qu'est-ce qui favorise l'apprentissage à long terme ?",
                        "explanation": "La répétition espacée et la pratique régulière.",
                        "choices": [
                            {"text": "Tout apprendre la veille de l'examen", "is_correct": False},
                            {"text": "La répétition espacée et la pratique régulière", "is_correct": True},
                            {"text": "Apprendre une seule fois", "is_correct": False},
                            {"text": "Ne jamais réviser", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Pourquoi est-il utile de travailler en groupe ?",
                        "explanation": "Partager des connaissances et résoudre des problèmes ensemble.",
                        "choices": [
                            {"text": "Pour partager des connaissances", "is_correct": True},
                            {"text": "Pour ne rien faire", "is_correct": False},
                            {"text": "Pour copier", "is_correct": False},
                            {"text": "Pour perdre du temps", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Qu'est-ce que la métacognition ?", "explanation": "Réfléchir à sa propre façon d'apprendre.",
                        "choices": [
                            {"text": "Apprendre par cœur", "is_correct": False},
                            {"text": "Réfléchir à sa propre façon d'apprendre", "is_correct": True},
                            {"text": "Un type de mémoire", "is_correct": False},
                            {"text": "Une technique de lecture", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Comment gérer la procrastination ?", "explanation": "Découper les tâches et fixer des objectifs réalistes.",
                        "choices": [
                            {"text": "Tout faire d'un coup", "is_correct": False},
                            {"text": "Découper les tâches et fixer des objectifs réalistes", "is_correct": True},
                            {"text": "Reporter au lendemain", "is_correct": False},
                            {"text": "Ne rien faire", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Pourquoi fixer des objectifs d'apprentissage ?", "explanation": "Pour rester motivé et mesurer sa progression.",
                        "choices": [
                            {"text": "Pour rester motivé et mesurer sa progression", "is_correct": True},
                            {"text": "Pour stresser", "is_correct": False},
                            {"text": "Ce n'est pas utile", "is_correct": False},
                            {"text": "Pour comparer aux autres", "is_correct": False},
                        ],
                    },
                    {
                        "title": "Que faire après avoir terminé un module ?", "explanation": "Réviser, faire un projet pratique et passer au suivant.",
                        "choices": [
                            {"text": "Réviser, faire un projet pratique et passer au suivant", "is_correct": True},
                            {"text": "Oublier tout", "is_correct": False},
                            {"text": "Ne rien faire", "is_correct": False},
                            {"text": "Recommencer du début", "is_correct": False},
                        ],
                    },
                ],
            },
        }
