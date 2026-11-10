import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils import timezone

from .models import Asset, ReminderDelivery, ReminderSettings
from .email_config import configured, email_connection

THRESHOLDS = (30, 15, 10, 5)
LEASE_DURATION = timedelta(minutes=5)


def reminder_running(options):
    return bool(options.lock_token and options.lock_until and options.lock_until > timezone.now())


def send_reminders():
    if not configured():
        return {"skipped": "smtp-not-configured", "sent": 0, "failed": 0}
    options = ReminderSettings.objects.get(pk=1)
    if not options.enabled:
        return {"skipped": "disabled", "sent": 0, "failed": 0}
    token = uuid.uuid4().hex
    now = timezone.now()
    acquired = ReminderSettings.objects.filter(pk=1, enabled=True).filter(
        Q(lock_until__isnull=True) | Q(lock_until__lte=now)
    ).update(lock_token=token, lock_until=now + LEASE_DURATION)
    if not acquired:
        return {"skipped": "already-running", "sent": 0, "failed": 0}
    result = {"sent": 0, "failed": 0, "skippedRecipients": 0}
    try:
        today = now.date()
        assets = Asset.objects.filter(status="active", expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).select_related("owner")
        for asset in assets.iterator():
            remaining = (asset.expiry_date - today).days
            threshold = next(value for value in reversed(THRESHOLDS) if remaining <= value)
            recipients = {email.strip().lower() for email in [
                asset.owner.email if asset.owner and asset.owner.is_active else "", asset.notification_email
            ] if email}
            if not recipients:
                result["skippedRecipients"] += 1
            for recipient in sorted(recipients):
                delivery_key = {"asset": asset, "expiry_date": asset.expiry_date, "threshold": threshold, "recipient": recipient}
                if ReminderDelivery.objects.filter(**delivery_key, state="sent").exists():
                    continue
                held = ReminderSettings.objects.filter(pk=1, lock_token=token, enabled=True).update(lock_until=timezone.now() + LEASE_DURATION)
                if not held:
                    result["skipped"] = "lock-lost-or-disabled"
                    return result
                state = "sent"
                error = ""
                try:
                    connection, sender = email_connection()
                    safe_name = asset.name.replace("\r", " ").replace("\n", " ")
                    expires = "today" if remaining == 0 else f"in {remaining} days"
                    message = EmailMessage(
                        subject=f"[Asset renewal] {safe_name} expires {expires}",
                        body="\n".join([
                            "AssetCairn", "", f"Asset: {asset.name}", f"Asset tag: {asset.tag}",
                            f"Category: {asset.category}", f"Registration date: {asset.registration_date}",
                            f"Expiry date: {asset.expiry_date}", f"Expected renewal date: {asset.renewal_date}",
                            f"Days until expiry: {remaining}", "", "Please arrange renewal before the expiry date.",
                            "", f"This is the {threshold}-day renewal reminder.",
                        ]),
                        from_email=sender, to=[recipient], connection=connection,
                    )
                    if message.send(fail_silently=False) != 1:
                        raise RuntimeError("Email backend did not accept the message")
                    result["sent"] += 1
                except Exception as failure:
                    state = "failed"
                    error = type(failure).__name__[:100]
                    result["failed"] += 1
                attempted_at = timezone.now()
                ReminderDelivery.objects.update_or_create(**delivery_key, defaults={
                    "state": state, "error": error, "sent_at": attempted_at if state == "sent" else None,
                    "attempted_at": attempted_at,
                })
        return result
    finally:
        ReminderSettings.objects.filter(pk=1, lock_token=token).update(lock_token="", lock_until=None)