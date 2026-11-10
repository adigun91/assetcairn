import base64
import io

from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from assets.models import Role, User


def image_data(format="PNG", size=(32, 32)):
    image = Image.new("RGB", size, color=(45, 100, 70))
    output = io.BytesIO()
    image.save(output, format=format)
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[format]
    return f"data:{mime};base64," + base64.b64encode(output.getvalue()).decode("ascii")


class ProfileAvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(name="Profile User", email="profile@example.com", password="ProfilePassword123!", role=Role.objects.get(name="Viewer"))
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        token = self.client.get("/api/auth/session").json()["csrfToken"]
        self.client.credentials(HTTP_X_CSRF_TOKEN=token)

    def test_profile_exposes_read_only_identity_and_uploads_normalized_avatar(self):
        response = self.client.get("/api/profile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "profile@example.com")
        self.assertEqual(response.json()["avatar"], "")
        self.assertIn("no-store", response["Cache-Control"])
        response = self.client.put("/api/profile", {"avatar": image_data("PNG", (1024, 800))}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertEqual(self.user.name, "Profile User")
        self.assertTrue(response.json()["avatar"].startswith("data:image/jpeg;base64,"))
        output = base64.b64decode(response.json()["avatar"].split(",", 1)[1])
        with Image.open(io.BytesIO(output)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 512)

    def test_profile_update_cannot_change_email_name_or_role(self):
        response = self.client.put("/api/profile", {"avatar": image_data(), "email": "attacker@example.com",
                                                     "name": "Changed Name", "role_id": Role.objects.get(name="Administrator").pk}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        self.assertEqual(self.user.name, "Profile User")
        self.assertEqual(self.user.role.name, "Viewer")

    def test_avatar_can_be_removed(self):
        self.client.put("/api/profile", {"avatar": image_data()}, format="json")
        response = self.client.put("/api/profile", {"avatar": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["avatar"], "")
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_data, "")

    def test_rejects_malformed_unsupported_mismatched_and_oversized_images(self):
        invalid_values = [
            "javascript:alert(1)",
            "data:image/svg+xml;base64," + base64.b64encode(b"<svg></svg>").decode("ascii"),
            "data:image/png;base64," + base64.b64encode(b"not an image").decode("ascii"),
            "data:image/jpeg;base64," + base64.b64encode(Image.new("RGB", (5, 5)).tobytes()).decode("ascii"),
            "data:image/png;base64," + base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode("ascii"),
        ]
        for value in invalid_values:
            with self.subTest(value=value[:32]):
                response = self.client.put("/api/profile", {"avatar": value}, format="json")
                self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_data, "")

    def test_avatar_is_private_to_authenticated_session_and_csrf_protected(self):
        anonymous = APIClient(enforce_csrf_checks=True)
        self.assertEqual(anonymous.get("/api/profile").status_code, 401)
        self.assertEqual(anonymous.put("/api/profile", {"avatar": image_data()}, format="json").status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.put("/api/profile", {"avatar": image_data()}, format="json").status_code, 200)