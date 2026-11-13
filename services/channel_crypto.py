import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from decouple import config
from django.conf import settings


def _fernet() -> Fernet:
    """Clé Fernet : CHANNELS_ENCRYPTION_KEY en priorité, dérivée de SECRET_KEY sinon.

    Générer une clé : python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = config('CHANNELS_ENCRYPTION_KEY', default='').strip()
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value:
        return ''
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ''
