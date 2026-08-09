from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from users.auth.models import AuthRateLimit, PhoneVerificationChallenge


class Command(BaseCommand):
    help = 'Delete expired auth rate-limit rows and old phone verification challenges.'

    def handle(self, *args, **options):
        now = timezone.now()
        rate_limits, _ = AuthRateLimit.objects.filter(expires_at__lt=now).delete()
        challenges, _ = PhoneVerificationChallenge.objects.filter(
            expires_at__lt=now - timedelta(days=1),
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {rate_limits} rate-limit rows and {challenges} verification challenges.'
            )
        )
