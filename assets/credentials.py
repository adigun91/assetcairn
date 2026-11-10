import json

from cryptography.exceptions import InvalidTag
from cryptography.fernet import InvalidToken
from django.conf import settings
from rest_framework import serializers

from .credential_crypto import decrypt_payload, encrypt_payload


def decrypt_credentials(asset):
    if not asset.credentials_encrypted:
        return {"username": "", "password": "", "url": ""}
    try:
        return json.loads(decrypt_payload(asset.credentials_encrypted, settings.SECRET_KEY).decode())
    except (InvalidToken, InvalidTag, ValueError):
        raise serializers.ValidationError("Unable to decrypt asset credentials. Restore the original Django secret or replace the credentials.") from None


class CredentialSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=254, allow_blank=True)
    password = serializers.CharField(max_length=4096, trim_whitespace=False, required=False, allow_blank=True, write_only=True)
    url = serializers.URLField(max_length=1000, allow_blank=True)

    def validate_url(self, value):
        if value and not value.lower().startswith(("https://", "http://")):
            raise serializers.ValidationError("Use an HTTP or HTTPS login URL")
        return value


def encrypt_credentials(data, asset=None):
    values = dict(data)
    if "password" not in values:
        values["password"] = decrypt_credentials(asset)["password"] if asset else ""
    if not any(values.values()):
        return ""
    return encrypt_payload(json.dumps(values).encode(), settings.SECRET_KEY)