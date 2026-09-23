"""
Automatic Superuser Creator for Hosted Environments (Render, Railway, VPS).

Reads credentials from environment variables:
  SUPERUSER / DJANGO_SUPERUSER_USERNAME (default: 'admin')
  SUPERUSER_PASSWORD / DJANGO_SUPERUSER_PASSWORD (default: 'Admin12345!')
  SUPERUSER_EMAIL / DJANGO_SUPERUSER_EMAIL (default: 'admin@sahasrarawellness.com')

Usage:
  python manage.py ensure_superuser
"""
import os
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically create or update the admin superuser from environment variables'

    def handle(self, *args, **options):
        username = (
            os.getenv('SUPERUSER') or 
            os.getenv('DJANGO_SUPERUSER_USERNAME') or 
            'admin'
        ).strip()
        
        password = (
            os.getenv('SUPERUSER_PASSWORD') or 
            os.getenv('DJANGO_SUPERUSER_PASSWORD') or 
            'Admin12345!'
        ).strip()
        
        email = (
            os.getenv('SUPERUSER_EMAIL') or 
            os.getenv('DJANGO_SUPERUSER_EMAIL') or 
            'admin@sahasrarawellness.com'
        ).strip()

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f' Successfully created superuser "{username}"'))
            logger.info('Created superuser %s via ensure_superuser command.', username)
        else:
            self.stdout.write(self.style.SUCCESS(f' Successfully updated credentials for superuser "{username}"'))
            logger.info('Updated credentials for superuser %s via ensure_superuser command.', username)
