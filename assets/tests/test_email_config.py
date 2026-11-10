from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assets.email_config import configured, read_config
from assets.models import ReminderSettings, Role, SecurityAuditEvent, User


@override_settings(SMTP_ALLOWED_HOSTS=["smtp.example.com"])
class EmailConfigurationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="smtp-admin@example.com", name="SMTP Admin", password="TestPassword123!", role=Role.objects.get(name="Administrator"))
        self.client = APIClient()
        self.client.force_login(self.admin)
        self.config = {"host": "smtp.example.com", "port": 587, "security": "starttls", "username": "sender@example.com",
                       "password": "test-only-smtp-password", "from_email": "sender@example.com"}

    def test_password_is_encrypted_and_never_returned(self):
        response = self.client.put("/api/reminders/email", self.config, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        event = SecurityAuditEvent.objects.get(action="smtp_destination_updated")
        self.assertEqual(event.metadata, {"host": "smtp.example.com", "port": 587})
        self.assertNotIn(self.config["password"], str(event.metadata))
        stored = ReminderSettings.objects.get(pk=1).smtp_config
        self.assertNotIn(self.config["password"], stored)
        self.assertEqual(read_config()["password"], self.config["password"])
        self.assertTrue(configured())
        response = self.client.get("/api/reminders/email")
        self.assertNotIn("password", response.json())
        self.assertTrue(response.json()["has_password"])
        self.assertEqual(response["Cache-Control"], "no-store")
        changed = {key: value for key, value in self.config.items() if key != "password"}
        changed["port"] = 465
        changed["security"] = "ssl"
        self.assertEqual(self.client.put("/api/reminders/email", changed, format="json").status_code, 200)
        self.assertEqual(read_config()["password"], self.config["password"])

    def test_viewers_cannot_read_or_change_email_settings(self):
        viewer = User.objects.create_user(email="viewer@example.com", name="Viewer", role=Role.objects.get(name="Viewer"))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get("/api/reminders/email").status_code, 403)
        self.assertEqual(self.client.put("/api/reminders/email", self.config, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/reminders/test-email", {"recipient": "test@example.com"}, format="json").status_code, 403)

    def test_invalid_configuration_is_rejected(self):
        for changes in [{"host": "https://smtp.example.com"}, {"port": 0}, {"security": "none"}, {"from_email": "invalid"}, {"password": ""}]:
            response = self.client.put("/api/reminders/email", self.config | changes, format="json")
            self.assertEqual(response.status_code, 400)

    def test_test_email_and_sanitized_errors(self):
        self.client.put("/api/reminders/email", self.config, format="json")
        with patch("django.core.mail.EmailMessage.send", return_value=1) as send:
            response = self.client.post("/api/reminders/test-email", {"recipient": "test@example.com"}, format="json")
            self.assertEqual(response.status_code, 200)
            send.assert_called_once()
        with patch("django.core.mail.EmailMessage.send", side_effect=RuntimeError(self.config["password"])):
            response = self.client.post("/api/reminders/test-email", {"recipient": "test@example.com"}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(self.config["password"], response.content.decode())

    @override_settings(REMINDERS_SMTP_CONFIGURED=False)
    def test_test_email_requires_configuration(self):
        response = self.client.post("/api/reminders/test-email", {"recipient": "test@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)