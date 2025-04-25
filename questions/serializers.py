from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from accounts.models import User
from core.serializers import TechnologySerializer
from questions.models import Question, Choice


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct', 'question']
        extra_kwargs = {
            'question': {'read_only': True},
        }


class PublisherSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    role = serializers.ChoiceField(choices=User.Roles.choices)
    email = serializers.EmailField()
    picture = serializers.URLField(allow_null=True)


class QuestionSerializer(WritableNestedModelSerializer):
    choices = ChoiceSerializer(many=True)
    publisher = serializers.SerializerMethodField()
    profession = serializers.SlugRelatedField(slug_field='title', read_only=True)
    technology = TechnologySerializer(read_only=True)

    class Meta:
        model = Question
        fields = '__all__'
        read_only_fields = ['publisher', 'status', 'technology']

    @extend_schema_field(PublisherSerializer)
    def get_publisher(self, obj: Question):
        return {
            'id': obj.publisher.id,
            'username': obj.publisher.username,
            'role': obj.publisher.role,
            'email': obj.publisher.email,
            'picture': obj.publisher.picture.url if obj.publisher.picture else None
        }

    @transaction.atomic
    def create(self, validated_data):
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.status = Question.Status.PENDING
        return instance
