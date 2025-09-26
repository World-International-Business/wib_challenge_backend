from functools import lru_cache

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count
from django.template.loader import render_to_string
from rest_framework import serializers


class TagsSerializerField(serializers.SlugRelatedField):

    def to_internal_value(self, data):
        try:
            obj, created = self.get_queryset().get_or_create(**{self.slug_field: data})
            return obj
        except (TypeError, ValueError):
            self.fail('invalid')


from apps.core.models import Profession, Technology, Domain


class _QuestionStatsSerializerMixin(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()

    @lru_cache(maxsize=4)
    def get_questions_count(self, obj) -> int:
        if not hasattr(obj, 'questions'):
            return obj.__class__.objects.filter(id=obj.id).annotate(
                count=Count('technologies__questions')
            ).values_list('count', flat=True).first() or 0
        return obj.questions.count()


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = '__all__'


class TechnologySerializer(_QuestionStatsSerializerMixin):
    class Meta:
        model = Technology
        fields = '__all__'


class ProfessionSerializer(_QuestionStatsSerializerMixin):
    domain_name = serializers.CharField(source='domain.name', read_only=True)

    class Meta:
        model = Profession
        exclude = ('technologies',)


class ProfessionDetailSerializer(ProfessionSerializer):
    technologies = TechnologySerializer(many=True, read_only=True)
    domain = DomainSerializer(read_only=True)

    class Meta:
        model = Profession
        fields = '__all__'


class ContactSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField()
    phone = serializers.CharField(required=False)
    message = serializers.CharField()
    object = serializers.CharField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        return attrs

    def send_email(self):
        """Envoie l'email de contact"""
        context = {
            'name': self.validated_data['name'],
            'email': self.validated_data['email'],
            'phone': self.validated_data.get('phone', ''),
            'object': self.validated_data['object'],
            'message': self.validated_data['message'],
        }

        html_message = render_to_string('emails/contact_email.html', context)
        text_message = render_to_string('emails/contact_email.txt', context)

        send_mail(
            subject=f"[Contact WIB] {self.validated_data['object']}",
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL or settings.DEFAULT_FROM_EMAIL],
            html_message=html_message,
            fail_silently=False,
        )

        confirmation_html = render_to_string('emails/contact_confirmation.html', context)
        confirmation_text = render_to_string('emails/contact_confirmation.txt', context)

        send_mail(
            subject="Confirmation de réception - WIB Challenge",
            message=confirmation_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.validated_data['email']],
            html_message=confirmation_html,
            fail_silently=True,
        )
