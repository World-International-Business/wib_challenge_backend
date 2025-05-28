from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count

from questions.models import Domain, Category, Criteria, Tag, Choice, Question


class CategoryInline(admin.TabularInline):
    model = Category
    extra = 1
    show_change_link = True


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['name', 'categories_count']
    search_fields = ['name']
    ordering = ['name']
    inlines = [CategoryInline]
    
    fieldsets = (
        ('Informations', {
            'fields': ['name']
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            categories_count=Count('categories', distinct=True)
        )
    
    @admin.display(description='Nombre de catégories', ordering='categories_count')
    def categories_count(self, obj):
        return getattr(obj, 'categories_count', obj.categories.count())

    def save_model(self, request, obj, form, change):
        if self.get_queryset(request).filter(name=obj.name.strip()).exists() and not change:
            raise ValidationError('Un domaine avec ce nom existe déjà')
        super().save_model(request, obj, form, change)


class CriteriaInline(admin.TabularInline):
    model = Criteria
    extra = 1
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'criteria_count', 'questions_count']
    list_filter = ['domain']
    search_fields = ['name', 'domain__name']
    ordering = ['domain__name', 'name']
    autocomplete_fields = ['domain']
    inlines = [CriteriaInline]
    
    fieldsets = (
        ('Informations', {
            'fields': ['name', 'domain']
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('domain').annotate(
            criteria_count=Count('criteria', distinct=True),
            questions_count=Count('questions', distinct=True)
        )
    
    @admin.display(description='Nombre de critères', ordering='criteria_count')
    def criteria_count(self, obj):
        return getattr(obj, 'criteria_count', obj.criteria.count())
    
    @admin.display(description='Nombre de questions', ordering='questions_count')
    def questions_count(self, obj):
        return getattr(obj, 'questions_count', obj.questions.count())


class TagInline(admin.TabularInline):
    model = Tag
    extra = 1
    show_change_link = True


@admin.register(Criteria)
class CriteriaAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'domain_name', 'tags_count']
    list_filter = ['category__domain', 'category']
    search_fields = ['name', 'category__name', 'category__domain__name']
    ordering = ['category__name', 'name']
    autocomplete_fields = ['category']
    inlines = [TagInline]
    
    fieldsets = (
        ('Informations', {
            'fields': ['name', 'category']
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'category__domain').annotate(
            tags_count=Count('tags', distinct=True)
        )
    
    @admin.display(description='Domaine', ordering='category__domain__name')
    def domain_name(self, obj):
        return obj.category.domain.name
    
    @admin.display(description='Nombre de tags', ordering='tags_count')
    def tags_count(self, obj):
        return getattr(obj, 'tags_count', obj.tags.count())


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'criteria', 'category_name', 'domain_name', 'questions_count']
    list_filter = ['criteria__category__domain', 'criteria__category', 'criteria']
    search_fields = ['name', 'criteria__name', 'criteria__category__name', 'criteria__category__domain__name']
    ordering = ['criteria__name', 'name']
    autocomplete_fields = ['criteria']
    
    fieldsets = (
        ('Informations', {
            'fields': ['name', 'criteria']
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'criteria', 'criteria__category', 'criteria__category__domain'
        ).annotate(
            questions_count=Count('questions', distinct=True)
        )
    
    @admin.display(description='Catégorie', ordering='criteria__category__name')
    def category_name(self, obj):
        return obj.criteria.category.name
    
    @admin.display(description='Domaine', ordering='criteria__category__domain__name')
    def domain_name(self, obj):
        return obj.criteria.category.domain.name
    
    @admin.display(description='Nombre de questions', ordering='questions_count')
    def questions_count(self, obj):
        return getattr(obj, 'questions_count', obj.questions.count())


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1
    fields = ['text', 'is_correct']


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['text', 'question', 'question_type', 'category_name', 'domain_name', 'is_correct']
    list_filter = ['is_correct', 'question__question_type', 'question__category__domain', 'question__category']
    search_fields = ['text', 'question__title', 'question__category__name', 'question__category__domain__name']
    ordering = ['question__title', 'text']
    autocomplete_fields = ['question']
    
    fieldsets = (
        ('Informations', {
            'fields': ['text', 'question', 'is_correct']
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'question', 'question__category', 'question__category__domain'
        )
    
    @admin.display(description='Type de question')
    def question_type(self, obj):
        return obj.question.get_question_type_display()
    
    @admin.display(description='Catégorie', ordering='question__category__name')
    def category_name(self, obj):
        return obj.question.category.name
    
    @admin.display(description='Domaine', ordering='question__category__domain__name')
    def domain_name(self, obj):
        return obj.question.category.domain.name

    def save_model(self, request, obj, form, change):
        if obj.question.question_type == Question.QuestionType.OPEN_ANSWER:
            raise ValidationError('Une question de type "Réponse ouverte" ne peut pas avoir de choix')
        choices = obj.question.choices.all()
        choices = [choice for choice in choices if choice != obj] + [obj]
        if not any([choice.is_correct for choice in choices]):
            raise ValidationError(
                f'La question {obj.question} doit avoir au moins un choix correct')

        super().save_model(request, obj, form, change)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'domain_name', 'question_type', 'level', 'created_at', 'choices_count', 'correct_choices_count', 'tags_display']
    search_fields = ['title', 'description', 'category__name', 'category__domain__name', 'tags__name']
    list_filter = ['level', 'question_type', 'category__domain', 'category', 'tags']
    ordering = ['-created_at', 'title']
    inlines = [ChoiceInline]
    filter_horizontal = ['tags']
    autocomplete_fields = ['category']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ['title', 'description', 'category']
        }),
        ('Classification', {
            'fields': ['tags', 'level', 'question_type'],
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'category', 'category__domain'
        ).prefetch_related(
            'tags', 'choices'
        ).annotate(
            choices_count=Count('choices', distinct=True),
            correct_choices_count=Count('choices', distinct=True, filter={'choices__is_correct': True})
        )
    
    @admin.display(description='Domaine', ordering='category__domain__name')
    def domain_name(self, obj):
        return obj.category.domain.name
    
    @admin.display(description='Nombre de choix', ordering='choices_count')
    def choices_count(self, obj):
        if obj.is_open_answer:
            return '-'
        return getattr(obj, 'choices_count', obj.choices.count())
    
    @admin.display(description='Choix corrects', ordering='correct_choices_count')
    def correct_choices_count(self, obj):
        if obj.is_open_answer:
            return '-'
        return getattr(obj, 'correct_choices_count', obj.choices.filter(is_correct=True).count())
    
    @admin.display(description='Tags')
    def tags_display(self, obj):
        return ", ".join([tag.name for tag in obj.tags.all()[:3]]) + (
            "..." if obj.tags.count() > 3 else ""
        )
