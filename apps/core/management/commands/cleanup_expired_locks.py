"""
management command: cleanup_expired_locks

Releases expired SlotLocks and transitions orphaned PENDING_PAYMENT
bookings to EXPIRED status.

Run via OS cron every 5 minutes:
  */5 * * * *  /path/to/venv/bin/python manage.py cleanup_expired_locks

On Render.com: add a Cron Job service with the same command.
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.bookings.models import SlotLock, Booking, BookingStatus


class Command(BaseCommand):
    help = 'Release expired slot locks and expire stale PENDING_PAYMENT bookings'

    def handle(self, *args, **options):
        now = timezone.now()

        # 1. Release expired, unreleased locks
        expired_locks = SlotLock.objects.filter(
            released=False,
            expires_at__lt=now,
        )
        count_locks = expired_locks.count()
        expired_locks.update(released=True)

        # 2. Expire PENDING_PAYMENT bookings older than 15 minutes with no active lock
        cutoff = now - timedelta(minutes=15)
        stale_bookings = Booking.objects.filter(
            status=BookingStatus.PENDING_PAYMENT,
            created_at__lt=cutoff,
        )
        count_bookings = 0
        for booking in stale_bookings:
            # Only expire if slot lock is also gone/released
            lock = booking.slot_lock
            if lock is None or lock.released or lock.expires_at < now:
                booking.expire(changed_by='system_cron')
                count_bookings += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'cleanup_expired_locks: released {count_locks} locks, '
                f'expired {count_bookings} bookings'
            )
        )
