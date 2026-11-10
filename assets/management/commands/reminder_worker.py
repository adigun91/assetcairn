import json
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from assets.reminders import send_reminders


class Command(BaseCommand):
    help = "Check on startup, then run daily at 08:00 UTC while this worker is running."

    def handle(self, *args, **options):
        self.stdout.write("Django reminders: startup check, then daily at 08:00 UTC")
        last_run = None
        try:
            while True:
                now = timezone.now()
                if last_run is None or (now.date() != last_run and now.hour >= 8):
                    close_old_connections()
                    try:
                        result = send_reminders()
                        self.stdout.write(f"{now.isoformat()} {json.dumps(result)}")
                        last_run = now.date()
                    except Exception as error:
                        self.stderr.write(f"Reminder run failed: {type(error).__name__}")
                time.sleep(30)
        except KeyboardInterrupt:
            self.stdout.write("Reminder worker stopped")