from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer


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
