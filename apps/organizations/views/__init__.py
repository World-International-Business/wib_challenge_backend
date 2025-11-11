from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.models import Organization, Notification
from apps.organizations.serializers import OrganizationSerializer, NotificationSerializer
from apps.organizations.permissions import IsOrganization


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'organization'):
            return Organization.objects.filter(id=self.request.user.organization.id)
        elif self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.none()


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsOrganization]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'organization'):
            return Notification.objects.none()
        return Notification.objects.filter(organization=user.organization).order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        qs = self.get_queryset().filter(is_read=False)
        return Response({'count': qs.count()})

    @action(detail=True, methods=['post'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        notif = self.get_object()
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=['is_read'])
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'], url_path='mark-all-as-read')
    def mark_all_as_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        updated = qs.update(is_read=True)
        return Response({'updated': True, 'count': updated})
