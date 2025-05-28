from django.db import models

from wib_challenge.enums import ExperienceLevel


class Domain(models.Model):
    name = models.CharField('Nom', max_length=255, unique=True)

    class Meta:
        verbose_name = 'Domaine'
        verbose_name_plural = 'Domaines'
        ordering = ['name']

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('Nom', max_length=255)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, verbose_name='Domaine', related_name='categories')

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['name']
        unique_together = [['name', 'domain']]

    def __str__(self):
        return self.name


class Criteria(models.Model):
    name = models.CharField('Nom', max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Catégorie', related_name='criteria')

    class Meta:
        verbose_name = 'Critère'
        verbose_name_plural = 'Critères'
        ordering = ['name']
        unique_together = [['name', 'category']]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField('Nom', max_length=255)
    criteria = models.ForeignKey(Criteria, on_delete=models.CASCADE, verbose_name='Catégorie',
                                 related_name='tags')

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['name', 'criteria'], name='unique_tag_per_criteria')
        ]

    def __str__(self):
        return self.criteria.category.domain.name + ' - ' + self.name


class Question(models.Model):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'MCQ', 'Choix multiple'
        UNIQUE_CHOICE = 'UCQ', 'Choix unique'
        OPEN_ANSWER = 'OA', 'Réponse ouverte'

    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Catégorie', related_name='questions')
    tags = models.ManyToManyField(Tag, verbose_name='Tags', related_name='questions', blank=True)
    title = models.CharField('Titre', max_length=255)
    description = models.TextField('Description', blank=True, null=True)
    level = models.IntegerField('Niveau', choices=ExperienceLevel.choices, default=ExperienceLevel.BEGINNER, blank=True)
    question_type = models.CharField('Type de question', choices=QuestionType.choices,
                                     default=QuestionType.OPEN_ANSWER, max_length=3)
    created_at = models.DateTimeField('Créée le', auto_now_add=True)

    class Meta:
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'

    def __str__(self):
        return self.get_question_type_display() + ' - ' + self.category.name + ' - ' + self.title

    @property
    def is_multiple_choice(self):
        return self.question_type == self.QuestionType.MULTIPLE_CHOICE

    @property
    def is_unique_choice(self):
        return self.question_type == self.QuestionType.UNIQUE_CHOICE

    @property
    def is_open_answer(self):
        return self.question_type == self.QuestionType.OPEN_ANSWER


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name='Question', related_name='choices')
    text = models.CharField('Texte', max_length=255)
    is_correct = models.BooleanField('Correcte', default=False)

    class Meta:
        verbose_name = 'Choix'
        verbose_name_plural = 'Choix'

    def __str__(self):
        return self.text
