import json

from django.core.management.base import BaseCommand, CommandError

from assets.reminders import send_reminders


class Command(BaseCommand):
    help = "Send due 30-, 15-, 10-, and 5-day asset expiry reminders once."

    def handle(self, *args, **options):
        result = send_reminders()
        self.stdout.write(json.dumps(result))
        if result["failed"]:
            raise CommandError(f"{result['failed']} reminder delivery attempts failed; check delivery history")