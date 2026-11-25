from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class RecruitmentResumeStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.EMAIL_RESUME_ROOT

    @property
    def location(self):
        private_root = Path(self.base_location).resolve()
        if private_root.is_relative_to(Path(settings.MEDIA_ROOT).resolve()):
            raise ImproperlyConfigured('EMAIL_RESUME_ROOT doit être hors de MEDIA_ROOT.')
        return str(private_root)

    def url(self, name):
        raise ValueError('authenticated_download_required')
