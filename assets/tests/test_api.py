from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assets.models import PERMISSIONS, Asset, ReminderSettings, Role, SetupLock, User


@override_settings(DEBUG=True, SETUP_TOKEN="")
class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_role, _ = Role.objects.get_or_create(name="Administrator", defaults={"permissions": list(PERMISSIONS), "system": True})
        cls.viewer_role, _ = Role.objects.get_or_create(name="Viewer", defaults={"permissions": [], "system": True})
        SetupLock.objects.get_or_create(pk=1)
        ReminderSettings.objects.get_or_create(pk=1)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        response = self.client.get("/api/auth/session")
        self.csrf = response.json()["csrfToken"]
        self.client.credentials(HTTP_X_CSRF_TOKEN=self.csrf)
        response = self.client.post("/api/auth/setup", {"name": "Test Admin", "email": "admin@example.com", "password": "LongTestPassword123!"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.csrf = response.json()["csrfToken"]
        self.client.credentials(HTTP_X_CSRF_TOKEN=self.csrf)
        self.admin = User.objects.get(email="admin@example.com")

    def test_authentication_and_csrf(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        self.assertEqual(anonymous.get("/api/assets").status_code, 401)
        self.assertEqual(anonymous.post("/api/auth/login", {}, format="json").status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.post("/api/roles", {}, format="json").status_code, 403)

    def test_setup_only_once_and_hashed_password(self):
        self.assertEqual(self.client.post("/api/auth/setup", {}, format="json").status_code, 409)
        self.assertNotEqual(self.admin.password, "LongTestPassword123!")
        self.assertTrue(self.admin.check_password("LongTestPassword123!"))

    def test_asset_crud_dates_and_duplicate_tags(self):
        payload = {"name": "Endpoint protection", "tag": "LIC-001", "category": "License", "registration_date": "2026-01-01",
                   "expiry_date": "2026-12-01", "renewal_date": "2026-11-25", "owner_id": self.admin.pk, "cost": 49.99,
                   "asset_price": 500, "renewal_price": 550}
        created = self.client.post("/api/assets", payload, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["owner_email"], "admin@example.com")
        self.assertEqual(created.json()["cost"], 49.99)
        self.assertEqual(created.json()["asset_price"], 500)
        self.assertEqual(created.json()["renewal_price"], 550)
        duplicate = self.client.post("/api/assets", {**payload, "tag": "lic-001"}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        invalid = self.client.post("/api/assets", {**payload, "tag": "BAD", "expiry_date": "2026-02-30"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        invalid = self.client.post("/api/assets", {**payload, "tag": "EARLY", "expiry_date": "2025-01-01"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        invalid = self.client.post("/api/assets", {**payload, "tag": "NO-OWNER", "owner_id": None}, format="json")
        self.assertEqual(invalid.status_code, 400)
        asset_id = created.json()["id"]
        response = self.client.put(f"/api/assets/{asset_id}", {**payload, "expiry_date": "2027-12-01", "renewal_date": "2027-11-25"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.delete(f"/api/assets/{asset_id}").status_code, 200)
        self.assertFalse(Asset.objects.exists())

    def test_asset_prices_are_nonnegative_and_hardware_depreciation_is_conditional(self):
        payload = {"name": "Laptop", "tag": "HW-DEP-001", "category": "Hardware", "registration_date": "2026-01-01",
                   "expiry_date": "2027-01-01", "renewal_date": "2026-12-01", "owner_id": self.admin.pk,
                   "asset_price": 1800, "renewal_price": 220, "depreciation_acquisition_cost": 1600,
                   "depreciation_salvage_value": 100, "depreciation_useful_life_months": 36,
                   "depreciation_method": "straight_line", "depreciation_start_date": "2026-01-01"}
        created = self.client.post("/api/assets", payload, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["depreciation_acquisition_cost"], 1600)
        self.assertEqual(created.json()["depreciation_useful_life_months"], 36)
        self.assertEqual(created.json()["depreciation_method"], "straight_line")
        self.assertEqual(created.json()["depreciation_salvage_value"], 100)
        invalid = self.client.post("/api/assets", {**payload, "tag": "HW-DEP-PARTIAL", "depreciation_method": ""}, format="json")
        self.assertEqual(invalid.status_code, 400)
        invalid = self.client.post("/api/assets", {**payload, "tag": "HW-DEP-SALVAGE", "depreciation_salvage_value": 1700}, format="json")
        self.assertEqual(invalid.status_code, 400)
        invalid = self.client.post("/api/assets", {**payload, "tag": "HW-DEP-LIFE", "depreciation_useful_life_months": 0}, format="json")
        self.assertEqual(invalid.status_code, 400)
        invalid = self.client.post("/api/assets", {**payload, "tag": "SW-DEP-001", "category": "Software"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        asset_id = created.json()["id"]
        non_hardware = {**payload, "category": "Software", "depreciation_acquisition_cost": None,
                        "depreciation_salvage_value": None, "depreciation_useful_life_months": None,
                        "depreciation_method": "", "depreciation_start_date": None}
        updated = self.client.put(f"/api/assets/{asset_id}", non_hardware, format="json")
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertIsNone(updated.json()["depreciation_acquisition_cost"])
        self.assertEqual(updated.json()["depreciation_method"], "")
        invalid = self.client.post("/api/assets", {**payload, "tag": "NEG-PRICE", "asset_price": -1}, format="json")
        self.assertEqual(invalid.status_code, 400)

    def test_last_administrator_and_system_roles_are_protected(self):
        response = self.client.put(f"/api/users/{self.admin.pk}", {"name": self.admin.name, "email": self.admin.email, "role_id": self.admin.role_id, "active": False}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.delete(f"/api/roles/{self.admin_role.pk}").status_code, 400)

    def test_custom_roles_enforce_server_permissions(self):
        role = self.client.post("/api/roles", {"name": "Auditor", "permissions": []}, format="json")
        self.assertEqual(role.status_code, 201)
        created = self.client.post("/api/users", {"name": "Audit User", "email": "audit@example.com", "password": "AnotherPassword123!", "role_id": role.json()["id"]}, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertNotIn("password", created.json())
        viewer = APIClient(enforce_csrf_checks=True)
        token = viewer.get("/api/auth/session").json()["csrfToken"]
        viewer.credentials(HTTP_X_CSRF_TOKEN=token)
        response = viewer.post("/api/auth/login", {"email": "AUDIT@example.com", "password": "AnotherPassword123!"}, format="json")
        self.assertEqual(response.status_code, 200)
        viewer.credentials(HTTP_X_CSRF_TOKEN=response.json()["csrfToken"])
        self.assertEqual(viewer.get("/api/assets").status_code, 200)
        self.assertEqual(viewer.get("/api/users").status_code, 403)
        self.assertEqual(viewer.post("/api/assets", {}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/roles/{role.json()['id']}").status_code, 400)
        self.client.put(f"/api/users/{created.json()['id']}", {"name": "Audit User", "email": "audit@example.com", "role_id": role.json()["id"], "active": False}, format="json")
        self.assertEqual(viewer.get("/api/assets").status_code, 401)

    def test_password_change_preserves_session(self):
        response = self.client.post("/api/auth/password", {"currentPassword": "LongTestPassword123!", "password": "DifferentSecureWord987!"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/assets").status_code, 200)
        self.assertTrue(Session.objects.exists())
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("DifferentSecureWord987!"))


@override_settings(DEBUG=False, SETUP_TOKEN="test-only-setup-token")
class ProductionSetupTests(TestCase):
    def test_setup_requires_private_token(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/session").json()["csrfToken"]
        client.credentials(HTTP_X_CSRF_TOKEN=token)
        data = {"name": "First Administrator", "email": "first@example.com", "password": "ProductionTestPassword123!"}
        self.assertEqual(client.post("/api/auth/setup", data, format="json").status_code, 403)
        self.assertFalse(User.objects.exists())
        response = client.post("/api/auth/setup", {**data, "setupToken": "test-only-setup-token"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

    @override_settings(SETUP_TOKEN="")
    def test_production_setup_refuses_missing_server_token(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/session").json()["csrfToken"]
        client.credentials(HTTP_X_CSRF_TOKEN=token)
        data = {"name": "First Administrator", "email": "first@example.com", "password": "ProductionTestPassword123!"}
        self.assertEqual(client.post("/api/auth/setup", data, format="json").status_code, 403)
        self.assertFalse(User.objects.exists())


@override_settings(DEBUG=True, SETUP_TOKEN="")
class SetupOrganizationEmailTests(TestCase):
    def test_initial_workspace_rejects_personal_email_domains(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/session").json()["csrfToken"]
        client.credentials(HTTP_X_CSRF_TOKEN=token)
        payload = {"name": "Workspace Admin", "email": "person@gmail.com", "password": "LongWorkspacePassword123!"}
        response = client.post("/api/auth/setup", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("organization's email", response.json()["error"])
        self.assertFalse(User.objects.filter(email="person@gmail.com").exists())
        response = client.post("/api/auth/setup", {**payload, "email": "person@company.example"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)