from cryptography.exceptions import InvalidTag
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import migrations

from assets.credential_crypto import PREFIX, decrypt_payload, encrypt_payload


def upgrade_credentials(apps, schema_editor):
    asset_model = apps.get_model("assets", "Asset")
    database = schema_editor.connection.alias
    for asset in asset_model.objects.using(database).exclude(credentials_encrypted="").iterator():
        if asset.credentials_encrypted.startswith(PREFIX):
            continue
        try:
            plaintext = decrypt_payload(asset.credentials_encrypted, settings.SECRET_KEY)
        except (InvalidToken, InvalidTag, ValueError):
            raise RuntimeError("Cannot migrate asset credentials. Restore the original Django secret and rerun migrate.") from None
        upgraded = encrypt_payload(plaintext, settings.SECRET_KEY)
        asset_model.objects.using(database).filter(pk=asset.pk).update(credentials_encrypted=upgraded)


class Migration(migrations.Migration):
    dependencies = [("assets", "0004_asset_credentials_encrypted")]
    operations = [migrations.RunPython(upgrade_credentials)]