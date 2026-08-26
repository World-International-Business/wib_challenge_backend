from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, ListView, TemplateView, UpdateView,
)

from challenges.forms import (
    CategoryForm, ChoiceFormSet, CriteriaForm, DomainForm, QuestionForm,
    TagForm, TestDurationProfileForm,
)
from challenges.models import TestDurationProfile
from questions.models import Category, Criteria, Domain, Question, Tag
from wib_challenge.enums import ExperienceLevel


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


# ------------------------------------------------------------------
# Profils de durée
# ------------------------------------------------------------------

class DurationProfileListView(StaffRequiredMixin, ListView):
    model = TestDurationProfile
    template_name = 'challenges/admin/duration_profile_list.html'
    context_object_name = 'duration_profiles'
    paginate_by = 20
    ordering = ['domain__name', 'experience_level']

    def get_queryset(self):
        qs = super().get_queryset().select_related('domain')
        domain_id = self.request.GET.get('domain')
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['domains'] = Domain.objects.order_by('name')
        context['domain_filter'] = self.request.GET.get('domain', '')
        return context


class DurationProfileCreateView(StaffRequiredMixin, CreateView):
    model = TestDurationProfile
    form_class = TestDurationProfileForm
    template_name = 'challenges/admin/duration_profile_form.html'
    success_url = reverse_lazy('duration_profile_list')

    def form_valid(self, form):
        messages.success(self.request, 'Profil de durée créé.')
        return super().form_valid(form)


class DurationProfileUpdateView(StaffRequiredMixin, UpdateView):
    model = TestDurationProfile
    form_class = TestDurationProfileForm
    template_name = 'challenges/admin/duration_profile_form.html'
    success_url = reverse_lazy('duration_profile_list')

    def form_valid(self, form):
        messages.success(self.request, 'Profil de durée mis à jour.')
        return super().form_valid(form)


class DurationProfileDeleteView(StaffRequiredMixin, DeleteView):
    model = TestDurationProfile
    success_url = reverse_lazy('duration_profile_list')
    template_name = 'challenges/admin/confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Profil de durée supprimé.')
        return super().delete(request, *args, **kwargs)


# ------------------------------------------------------------------
# Gestion des profils / catégories / critères / compétences
# ------------------------------------------------------------------

class ProfileManagerView(StaffRequiredMixin, TemplateView):
    template_name = 'challenges/admin/profile_manager.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['domain_form'] = DomainForm(prefix='domain')
        context['category_form'] = CategoryForm(prefix='category')
        context['criteria_form'] = CriteriaForm(prefix='criteria')
        context['tag_form'] = TagForm(prefix='tag')
        context['domains'] = Domain.objects.prefetch_related('categories__criteria__tags').order_by('name')
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        form_map = {
            'add_domain': DomainForm,
            'add_category': CategoryForm,
            'add_criteria': CriteriaForm,
            'add_tag': TagForm,
        }
        form_class = form_map.get(action)
        if not form_class:
            messages.error(request, 'Action non reconnue.')
            return redirect('profile_manager')

        form = form_class(request.POST, prefix=action.replace('add_', ''))
        if form.is_valid():
            form.save()
            messages.success(request, f'{form.instance} ajouté.')
            return redirect('profile_manager')

        context = self.get_context_data()
        # réinjecte le formulaire invalide avec le bon préfixe
        context[f'{action.replace("add_", "")}_form'] = form
        return self.render_to_response(context)


# ------------------------------------------------------------------
# Questions par profil
# ------------------------------------------------------------------

class QuestionListView(StaffRequiredMixin, ListView):
    model = Question
    template_name = 'challenges/admin/question_list.html'
    context_object_name = 'questions'
    paginate_by = 20

    def get_queryset(self):
        qs = Question.objects.select_related('category__domain').prefetch_related('tags').order_by('-created_at')

        self.domain_id = self.request.GET.get('domain')
        self.category_id = self.request.GET.get('category')
        self.question_category = self.request.GET.get('question_category')
        self.question_type = self.request.GET.get('question_type')
        self.level = self.request.GET.get('level')
        self.search = self.request.GET.get('search', '').strip()

        if self.domain_id:
            qs = qs.filter(category__domain_id=self.domain_id)
        if self.category_id:
            qs = qs.filter(category_id=self.category_id)
        if self.question_category:
            qs = qs.filter(question_category=self.question_category)
        if self.question_type:
            qs = qs.filter(question_type=self.question_type)
        if self.level:
            qs = qs.filter(level=self.level)
        if self.search:
            qs = qs.filter(Q(title__icontains=self.search) | Q(description__icontains=self.search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['domains'] = Domain.objects.order_by('name')
        context['categories'] = Category.objects.order_by('name')
        context['domain_id'] = self.request.GET.get('domain', '')
        context['category_id'] = self.request.GET.get('category', '')
        context['question_category_choices'] = Question.QuestionCategory.choices
        context['question_type_choices'] = Question.QuestionType.choices
        context['level_choices'] = ExperienceLevel.choices
        context['question_category'] = self.request.GET.get('question_category', '')
        context['question_type'] = self.request.GET.get('question_type', '')
        context['level'] = self.request.GET.get('level', '')
        context['search'] = self.request.GET.get('search', '')
        return context


class QuestionCreateView(StaffRequiredMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = 'challenges/admin/question_form.html'

    def get_success_url(self):
        return reverse('question_list') + '?' + self.request.GET.urlencode()

    def get_initial(self):
        initial = super().get_initial()
        if 'question_category' in self.request.GET:
            initial['question_category'] = self.request.GET['question_category']
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = ChoiceFormSet(self.request.POST, prefix='choices')
        else:
            context['formset'] = ChoiceFormSet(prefix='choices')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            messages.success(self.request, 'Question créée.')
            return HttpResponseRedirect(self.get_success_url())
        return self.render_to_response(context)


class QuestionUpdateView(StaffRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'challenges/admin/question_form.html'

    def get_success_url(self):
        return reverse('question_list') + '?' + self.request.GET.urlencode()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = ChoiceFormSet(self.request.POST, instance=self.object, prefix='choices')
        else:
            context['formset'] = ChoiceFormSet(instance=self.object, prefix='choices')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            messages.success(self.request, 'Question mise à jour.')
            return HttpResponseRedirect(self.get_success_url())
        return self.render_to_response(context)


class QuestionDeleteView(StaffRequiredMixin, DeleteView):
    model = Question
    success_url = reverse_lazy('question_list')
    template_name = 'challenges/admin/confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Question supprimée.')
        return super().delete(request, *args, **kwargs)


# Variables utilisées par urls.py (compatibilité avec les vues fonctions)
duration_profile_list_view = DurationProfileListView.as_view()
duration_profile_create_view = DurationProfileCreateView.as_view()
duration_profile_update_view = DurationProfileUpdateView.as_view()
duration_profile_delete_view = DurationProfileDeleteView.as_view()
profile_manager_view = ProfileManagerView.as_view()
question_list_view = QuestionListView.as_view()
question_create_view = QuestionCreateView.as_view()
question_update_view = QuestionUpdateView.as_view()
question_delete_view = QuestionDeleteView.as_view()
