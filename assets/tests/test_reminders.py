from datetime import date, datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from assets.models import Asset, ReminderDelivery, ReminderSettings, Role, User
from assets.reminders import send_reminders


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", REMINDERS_SMTP_CONFIGURED=True,
                   DEFAULT_FROM_EMAIL="assets@example.com", EMAIL_HOST="smtp.example.com",
                   SMTP_ALLOWED_HOSTS=["smtp.example.com"])
class ReminderTests(TestCase):
    def setUp(self):
        role = Role.objects.get(name="Administrator")
        self.owner = User.objects.create_user(email="owner@example.com", password="TestPassword123!", name="Asset Owner", role=role)
        self.asset = Asset.objects.create(name="Laptop warranty", tag="HW-001", category="Hardware", registration_date=date(2026, 1, 1),
                                          expiry_date=date(2026, 12, 1), renewal_date=date(2026, 11, 25), owner=self.owner, notification_email="OWNER@example.com")
        self.options = ReminderSettings.objects.get(pk=1)

    def run_on(self, day):
        now = datetime.fromisoformat(f"{day}T08:00:00+00:00")
        with patch("assets.reminders.timezone.now", return_value=now):
            return send_reminders()

    def test_all_thresholds_send_once_to_deduplicated_recipients(self):
        for day, threshold in [("2026-11-01", 30), ("2026-11-16", 15), ("2026-11-21", 10), ("2026-11-26", 5)]:
            self.assertEqual(self.run_on(day)["sent"], 1)
            self.assertEqual(self.run_on(day)["sent"], 0)
            self.assertIn(f"This is the {threshold}-day", mail.outbox[-1].body)
            self.assertIn("Expected renewal date: 2026-11-25", mail.outbox[-1].body)
            self.assertEqual(mail.outbox[-1].to, ["owner@example.com"])
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(ReminderDelivery.objects.filter(state="sent").count(), 4)

    def test_catch_up_uses_only_current_threshold_and_renewal_resets(self):
        self.assertEqual(self.run_on("2026-11-27")["sent"], 1)
        self.assertIn("5-day", mail.outbox[0].body)
        self.assertEqual(self.run_on("2026-11-27")["sent"], 0)
        self.asset.expiry_date = date(2026, 12, 27)
        self.asset.save()
        self.assertEqual(self.run_on("2026-11-27")["sent"], 1)
        self.assertIn("30-day", mail.outbox[1].body)

    def test_failed_sends_are_recorded_and_retried(self):
        with patch("assets.reminders.EmailMessage.send", side_effect=ConnectionError("sensitive transport details")):
            self.assertEqual(self.run_on("2026-11-01")["failed"], 1)
        delivery = ReminderDelivery.objects.get()
        self.assertEqual(delivery.state, "failed")
        self.assertIsNone(delivery.sent_at)
        self.assertEqual(delivery.error, "ConnectionError")
        self.assertEqual(self.run_on("2026-11-01")["sent"], 1)
        self.assertEqual(self.run_on("2026-11-01")["sent"], 0)

    def test_paused_expired_retired_or_unconfigured_assets_do_not_send(self):
        self.options.enabled = False
        self.options.save()
        self.assertEqual(self.run_on("2026-11-01")["skipped"], "disabled")
        self.options.enabled = True
        self.options.save()
        self.asset.status = "retired"
        self.asset.save()
        self.assertEqual(self.run_on("2026-11-01")["sent"], 0)
        self.asset.status = "active"
        self.asset.save()
        self.assertEqual(self.run_on("2026-12-02")["sent"], 0)
        with override_settings(REMINDERS_SMTP_CONFIGURED=False):
            self.assertEqual(self.run_on("2026-11-01")["skipped"], "smtp-not-configured")

    def test_lock_prevents_overlapping_runs_and_expired_lock_recovers(self):
        frozen = datetime(2026, 11, 1, 8, tzinfo=datetime_timezone.utc)
        self.options.lock_token = "other-worker"
        self.options.lock_until = frozen + timedelta(minutes=5)
        self.options.save()
        self.assertEqual(self.run_on("2026-11-01")["skipped"], "already-running")
        self.options.lock_until = frozen - timedelta(minutes=1)
        self.options.save()
        self.assertEqual(self.run_on("2026-11-01")["sent"], 1)
        self.options.refresh_from_db()
        self.assertEqual(self.options.lock_token, "")

    def test_inactive_owner_and_additional_recipient(self):
        self.owner.is_active = False
        self.owner.save()
        self.asset.notification_email = "it@example.com"
        self.asset.save()
        self.assertEqual(self.run_on("2026-11-01")["sent"], 1)
        self.assertEqual(mail.outbox[0].to, ["it@example.com"])

    def test_management_command_runs_the_same_sender(self):
        with patch("assets.reminders.timezone.now", return_value=datetime(2026, 11, 1, 23, 59, tzinfo=datetime_timezone.utc)):
            call_command("send_reminders")
        self.assertEqual(len(mail.outbox), 1)