from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from questions.models import Question, Choice


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = '__all__'
        extra_kwargs = {
            'question': {'read_only': True},
        }


class _NestedChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['text', 'is_correct']
        extra_kwargs = {
            'question': {'read_only': True},
            'is_correct': {'required': False},
        }


class _ValidateChoiceMixin:

    def validate_choices(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(_('Au moins deux choix sont requis.'))
        if getattr(self.Meta, 'nested_question', False):
            return value
        if not any(choice['is_correct'] for choice in value):
            raise serializers.ValidationError(_('Au moins un choix doit être correct.'))
        if all(choice['is_correct'] for choice in value):
            raise serializers.ValidationError(_('Au moins un choix doit être incorrect.'))
        return value


class _NestedQuestionSerializer(_ValidateChoiceMixin, serializers.ModelSerializer):
    choices = _NestedChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ['text', 'explanation', 'language', 'choices']
        nested_question = True


class QuestionSerializer(_ValidateChoiceMixin, serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True)
    translated = _NestedQuestionSerializer(required=False)
    publisher = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = '__all__'

    @extend_schema_field(
        inline_serializer(
            name='Publisher',
            fields={
                'id': serializers.IntegerField(),
                'username': serializers.UUIDField(),
                'role': serializers.ChoiceField(choices=get_user_model().Roles.choices),
                'email': serializers.EmailField(),
                'picture': serializers.URLField(allow_null=True),
            }
        )
    )
    def get_publisher(self, obj: Question):
        return {
            'id': obj.publisher.id,
            'username': obj.publisher.username,
            'role': obj.publisher.role,
            'email': obj.publisher.email,
            'picture': obj.publisher.picture.url if obj.publisher.picture else None
        }

    def create_question(self, data):
        choices_data = data.pop('choices', [])
        question = Question.objects.create(**data)
        for choice_data in choices_data:
            Choice.objects.create(question=question, **choice_data)
        return question

    @transaction.atomic
    def create(self, validated_data):
        translated_data = validated_data.pop('translated', None)
        if translated_data:
            for (choices1, choices2) in zip(validated_data['choices'], translated_data['choices']):
                choices2['is_correct'] = choices1['is_correct']
            translated = self.create_question({**validated_data, **translated_data})

        question = self.create_question(validated_data)
        if translated_data:
            question.translated = translated
        question.save()
        return question

    def update_question(self, instance, validated_data):
        choices_data = validated_data.pop('choices', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.choices.all().delete()
        for choice_data in choices_data:
            Choice.objects.create(question=instance, **choice_data)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        translated_data = validated_data.pop('translated', None)
        if translated_data:
            for (choices1, choices2) in zip(validated_data['choices'], translated_data['choices']):
                choices2['is_correct'] = choices1['is_correct']
            translated_data = {**validated_data, **translated_data}
            if instance.translated:
                translated = self.update_question(instance.translated, translated_data)
            else:
                translated = self.create_question(translated_data)
            instance.translated = translated
        instance = self.update_question(instance, validated_data)
        instance.save()
        return instance
