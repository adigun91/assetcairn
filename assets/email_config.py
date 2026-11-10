import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.mail import get_connection
from rest_framework import serializers

from .models import ReminderSettings


def cipher():
    material = ("lifecycle:smtp:v1:" + settings.SECRET_KEY).encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(material).digest()))


def read_config():
    stored = ReminderSettings.objects.get(pk=1).smtp_config
    if stored:
        try:
            return json.loads(cipher().decrypt(stored.encode()).decode())
        except (InvalidToken, ValueError):
            raise serializers.ValidationError("Unable to decrypt SMTP settings. Restore the original Django secret or save new settings.") from None
    return {"host": settings.EMAIL_HOST, "port": settings.EMAIL_PORT,
            "security": "ssl" if settings.EMAIL_USE_SSL else "starttls",
            "username": settings.EMAIL_HOST_USER, "password": settings.EMAIL_HOST_PASSWORD,
            "from_email": settings.DEFAULT_FROM_EMAIL}


def configured():
    if not ReminderSettings.objects.get(pk=1).smtp_config:
        return settings.REMINDERS_SMTP_CONFIGURED
    config = read_config()
    return bool(config["host"] and config["from_email"] and bool(config["username"]) == bool(config["password"]))


def validate_smtp_host(host):
    normalized = host.strip().lower()
    if normalized not in settings.SMTP_ALLOWED_HOSTS:
        raise serializers.ValidationError({"host": "SMTP host is not in the SMTP_ALLOWED_HOSTS allowlist."})
    return normalized


def public_config():
    config = read_config()
    return {key: value for key, value in config.items() if key != "password"} | {
        "has_password": bool(config["password"]),
        "source": "saved" if ReminderSettings.objects.get(pk=1).smtp_config else "environment",
    }


class SMTPConfigSerializer(serializers.Serializer):
    host = serializers.RegexField(r"^[a-zA-Z0-9][a-zA-Z0-9.-]*$", max_length=253)
    port = serializers.IntegerField(min_value=1, max_value=65535)
    security = serializers.ChoiceField(choices=["starttls", "ssl"])
    username = serializers.CharField(max_length=254, allow_blank=True)
    password = serializers.CharField(max_length=4096, trim_whitespace=False, required=False, allow_blank=True, write_only=True)
    from_email = serializers.EmailField(max_length=254)

    def validate(self, attrs):
        attrs["host"] = validate_smtp_host(attrs["host"])
        if "password" not in attrs:
            attrs["password"] = read_config()["password"]
        if bool(attrs["username"]) != bool(attrs["password"]):
            raise serializers.ValidationError("Provide both SMTP username and password, or leave both empty for an unauthenticated relay.")
        return attrs


def save_config(config):
    encrypted = cipher().encrypt(json.dumps(config).encode()).decode()
    ReminderSettings.objects.filter(pk=1).update(smtp_config=encrypted)


def email_connection():
    config = read_config()
    validate_smtp_host(config["host"])
    if not ReminderSettings.objects.get(pk=1).smtp_config:
        return get_connection(), config["from_email"]
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend", host=config["host"], port=config["port"],
        username=config["username"], password=config["password"], use_tls=config["security"] == "starttls",
        use_ssl=config["security"] == "ssl", timeout=20,
    ), config["from_email"]