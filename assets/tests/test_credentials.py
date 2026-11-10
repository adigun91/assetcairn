import base64
import hashlib
import importlib
import json
from types import SimpleNamespace

from cryptography.fernet import Fernet
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assets.models import Asset, Role, SecurityAuditEvent, User
from assets.credential_crypto import PREFIX, asset_key
from assets.credentials import decrypt_credentials


class AssetCredentialTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(email="manager@example.com", name="Manager", role=Role.objects.get(name="Asset Manager"))
        self.owner = User.objects.create_user(email="owner@example.com", name="Owner", role=Role.objects.get(name="Viewer"))
        self.other = User.objects.create_user(email="other@example.com", name="Other", role=Role.objects.get(name="Viewer"))
        self.client = APIClient()
        self.client.force_login(self.manager)
        self.payload = {"name": "Managed license", "tag": "CRED-001", "category": "License", "registration_date": "2026-01-01",
                        "expiry_date": "2026-12-01", "renewal_date": "2026-11-25", "owner_id": self.owner.pk,
                        "credentials": {"username": "asset-account@example.com", "password": "TestAssetSecret123!", "url": "https://example.com/login"}}
        response = self.client.post("/api/assets", self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.asset = Asset.objects.get(pk=response.json()["id"])
        self.endpoint = f"/api/assets/{self.asset.pk}/credentials"

    def test_encrypted_and_not_in_list_responses(self):
        self.assertTrue(self.asset.credentials_encrypted.startswith(PREFIX))
        self.assertEqual(len(asset_key(settings.SECRET_KEY)), 32)
        self.assertNotIn("TestAssetSecret123!", self.asset.credentials_encrypted)
        self.assertNotIn("asset-account@example.com", self.asset.credentials_encrypted)
        response = self.client.get("/api/assets")
        self.assertTrue(response.json()[0]["has_credentials"])
        self.assertNotIn("credentials", response.json()[0])
        self.assertNotIn("credentials_encrypted", response.json()[0])
        self.assertNotIn("TestAssetSecret123!", response.content.decode())
        response = self.client.get(self.endpoint)
        self.assertEqual(response.json(), self.payload["credentials"])
        self.assertIn("no-store", response["Cache-Control"])
        event = SecurityAuditEvent.objects.get(action="credential_viewed")
        self.assertEqual(event.actor, self.manager)
        self.assertEqual(event.asset, self.asset)
        self.assertNotIn(self.payload["credentials"]["password"], str(event.metadata))

    def test_credential_mutations_are_audited_without_secret_values(self):
        self.client.put(self.endpoint, {"username": "updated", "password": "AnotherSecret123!"}, format="json")
        self.client.delete(self.endpoint)
        actions = list(SecurityAuditEvent.objects.order_by("created_at").values_list("action", flat=True))
        self.assertEqual(actions, ["credential_created", "credential_removed"])
        self.assertNotIn("AnotherSecret123!", str(list(SecurityAuditEvent.objects.values("metadata"))))

    def test_owner_access_and_unassigned_viewer_denied(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.endpoint).status_code, 200)
        self.assertEqual(self.client.put(self.endpoint, self.payload["credentials"], format="json").status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)
        self.assertEqual(self.client.delete(self.endpoint).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.endpoint).status_code, 401)

    def test_preserve_replace_and_remove(self):
        updated = {key: value for key, value in self.payload.items() if key != "credentials"}
        self.assertEqual(self.client.put(f"/api/assets/{self.asset.pk}", updated, format="json").status_code, 200)
        self.assertEqual(self.client.get(self.endpoint).json()["password"], "TestAssetSecret123!")
        credentials = {"username": "changed", "url": "https://example.com"}
        self.assertEqual(self.client.put(self.endpoint, credentials, format="json").status_code, 200)
        self.assertEqual(self.client.get(self.endpoint).json()["password"], "TestAssetSecret123!")
        self.client.put(self.endpoint, {**credentials, "password": "Replacement123!"}, format="json")
        self.assertEqual(self.client.get(self.endpoint).json()["password"], "Replacement123!")
        self.assertEqual(self.client.delete(self.endpoint).status_code, 200)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.credentials_encrypted, "")

    def test_invalid_login_url_rejected_and_reassignment_revokes_access(self):
        self.assertEqual(self.client.put(self.endpoint, {"username": "user", "url": "ftp://example.com"}, format="json").status_code, 400)
        self.asset.owner = self.other
        self.asset.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)

    def test_reveal_requires_active_session(self):
        self.manager.is_active = False
        self.manager.save()
        self.assertEqual(self.client.get(self.endpoint).status_code, 401)

    def test_fresh_nonce_for_each_write(self):
        original = self.asset.credentials_encrypted
        self.client.put(self.endpoint, self.payload["credentials"], format="json")
        self.asset.refresh_from_db()
        self.assertNotEqual(original, self.asset.credentials_encrypted)
        self.assertEqual(decrypt_credentials(self.asset), self.payload["credentials"])

    def test_tampering_and_wrong_key_fail_without_exposing_credentials(self):
        original = self.asset.credentials_encrypted
        payload = bytearray(base64.urlsafe_b64decode(original[len(PREFIX):]))
        payload[-1] ^= 1
        self.asset.credentials_encrypted = PREFIX + base64.urlsafe_b64encode(payload).decode()
        self.asset.save()
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("TestAssetSecret123!", response.content.decode())
        self.asset.credentials_encrypted = original
        self.asset.save()
        with override_settings(SECRET_KEY="different-test-encryption-secret"):
            self.client.force_login(self.manager)
            response = self.client.get(self.endpoint)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("TestAssetSecret123!", response.content.decode())

    def test_legacy_migration_preserves_credentials_and_is_idempotent(self):
        material = ("lifecycle:asset-credentials:v1:" + settings.SECRET_KEY).encode()
        legacy = Fernet(base64.urlsafe_b64encode(hashlib.sha256(material).digest()))
        self.asset.credentials_encrypted = legacy.encrypt(json.dumps(self.payload["credentials"]).encode()).decode()
        self.asset.save()
        migration = importlib.import_module("assets.migrations.0005_asset_credentials_aes256")
        editor = SimpleNamespace(connection=connection)
        migration.upgrade_credentials(apps, editor)
        self.asset.refresh_from_db()
        self.assertTrue(self.asset.credentials_encrypted.startswith(PREFIX))
        self.assertEqual(decrypt_credentials(self.asset), self.payload["credentials"])
        original = self.asset.credentials_encrypted
        migration.upgrade_credentials(apps, editor)
        self.asset.refresh_from_db()
        self.assertEqual(original, self.asset.credentials_encrypted)