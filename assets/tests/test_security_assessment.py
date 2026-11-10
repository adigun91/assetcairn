from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assets.email_config import email_connection
from assets.models import Asset, Role, User


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
class SecurityAssessmentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(name="Security Test Admin", email="security-admin@example.com",
                                              password="SecurityTestPassword123!", role=Role.objects.get(name="Administrator"))
        self.viewer = User.objects.create_user(name="Security Viewer", email="security-viewer@example.com",
                                               password="ViewerTestPassword123!", role=Role.objects.get(name="Viewer"))
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        self.token = self.client.get("/api/auth/session").json()["csrfToken"]
        self.client.credentials(HTTP_X_CSRF_TOKEN=self.token)

    def tearDown(self):
        cache.clear()

    def test_hostile_origin_is_rejected_even_with_valid_csrf_token(self):
        response = self.client.post("/api/roles", {"name": "Origin Test", "permissions": []},
                                    format="json", HTTP_ORIGIN="https://untrusted.example")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Role.objects.filter(name="Origin Test").exists())

    def test_malformed_json_and_wrong_methods_return_controlled_errors(self):
        response = self.client.generic("POST", "/api/assets", b'{"name":', content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertNotIn("Traceback", response.content.decode())
        self.assertEqual(self.client.patch("/api/assets", {}, format="json").status_code, 405)

    def test_sql_injection_login_does_not_bypass_authentication(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        token = anonymous.get("/api/auth/session").json()["csrfToken"]
        anonymous.credentials(HTTP_X_CSRF_TOKEN=token)
        response = anonymous.post("/api/auth/login", {"email": "admin' OR '1'='1", "password": "irrelevant"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(anonymous.get("/api/assets").status_code, 401)

    def test_mass_assignment_cannot_grant_superuser_or_staff(self):
        payload = {"name": "New Viewer", "email": "new-viewer@example.com", "password": "LongViewerPassword123!",
                   "role_id": self.viewer.role_id, "is_superuser": True, "is_staff": True, "permissions": ["roles:manage"]}
        response = self.client.post("/api/users", payload, format="json")
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(email="new-viewer@example.com")
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)
        self.assertEqual(created.role.permissions, [])

    def test_logout_invalidates_copied_session_cookie(self):
        copied = APIClient()
        copied.cookies["asset.sid"] = self.client.cookies["asset.sid"].value
        self.assertEqual(copied.get("/api/assets").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(copied.get("/api/assets").status_code, 401)

    def test_password_reset_invalidates_existing_user_session(self):
        old_session = APIClient()
        old_session.force_login(self.viewer)
        response = self.client.put(f"/api/users/{self.viewer.pk}", {
            "name": self.viewer.name, "email": self.viewer.email, "role_id": self.viewer.role_id,
            "active": True, "password": "ChangedViewerPassword123!",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(old_session.get("/api/assets").status_code, 401)

    def test_permission_changes_apply_to_existing_sessions(self):
        custom = Role.objects.create(name="Temporary Asset Manager", permissions=["assets:write"])
        self.viewer.role = custom
        self.viewer.save()
        viewer_client = APIClient(enforce_csrf_checks=True)
        viewer_client.force_login(self.viewer)
        token = viewer_client.get("/api/auth/session").json()["csrfToken"]
        viewer_client.credentials(HTTP_X_CSRF_TOKEN=token)
        response = self.client.put(f"/api/roles/{custom.pk}", {"name": custom.name, "permissions": []}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(viewer_client.post("/api/assets", {}, format="json").status_code, 403)

    def test_login_throttle_is_per_ip_in_one_process(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        token = anonymous.get("/api/auth/session").json()["csrfToken"]
        anonymous.credentials(HTTP_X_CSRF_TOKEN=token)
        with patch("assets.views.authenticate", return_value=None):
            for attempt in range(30):
                response = anonymous.post("/api/auth/login", {"email": "missing@example.com", "password": "test-only"}, format="json")
                self.assertEqual(response.status_code, 401)
            response = anonymous.post("/api/auth/login", {"email": "missing@example.com", "password": "test-only"}, format="json")
            self.assertEqual(response.status_code, 429)
            response = anonymous.post("/api/auth/login", {"email": "missing@example.com", "password": "test-only"},
                                      format="json", REMOTE_ADDR="192.0.2.20")
            self.assertEqual(response.status_code, 401)

    @override_settings(SMTP_ALLOWED_HOSTS=["smtp.example.com"])
    def test_smtp_destination_must_be_allowlisted(self):
        payload = {"host": "127.0.0.1", "port": 2525, "security": "starttls", "username": "", "password": "",
                   "from_email": "test@example.com"}
        self.assertEqual(self.client.put("/api/reminders/email", payload, format="json").status_code, 400)
        payload["host"] = "smtp.example.com"
        response = self.client.put("/api/reminders/email", payload, format="json")
        self.assertEqual(response.status_code, 200)
        with patch("assets.email_config.get_connection") as mocked:
            email_connection()
            self.assertEqual(mocked.call_args.kwargs["host"], "smtp.example.com")

    @override_settings(SMTP_ALLOWED_HOSTS=["127.0.0.1"])
    def test_explicitly_allowlisted_private_smtp_relay_is_supported(self):
        payload = {"host": "127.0.0.1", "port": 2525, "security": "starttls", "username": "", "password": "",
                   "from_email": "test@example.com"}
        self.assertEqual(self.client.put("/api/reminders/email", payload, format="json").status_code, 200)

    def test_security_headers_include_content_security_policy(self):
        response = self.client.get("/")
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertIn("object-src 'none'", response["Content-Security-Policy"])
        self.assertNotIn("X-Powered-By", response.headers)
        self.assertFalse(response.headers.get("Server"))

    @override_settings(MAX_REQUEST_BODY_SIZE=128, DATA_UPLOAD_MAX_MEMORY_SIZE=None)
    def test_json_parser_rejects_body_above_configured_limit(self):
        payload = {"name": "Small limit probe", "tag": "LIMIT-001", "category": "Hardware",
                   "registration_date": "2026-01-01", "expiry_date": "2027-01-01", "renewal_date": "2026-12-01",
                   "owner_id": self.admin.pk, "notes": "a" * 512}
        response = self.client.post("/api/assets", payload, format="json")
        self.assertEqual(response.status_code, 413)
        self.assertFalse(Asset.objects.filter(tag="LIMIT-001").exists())