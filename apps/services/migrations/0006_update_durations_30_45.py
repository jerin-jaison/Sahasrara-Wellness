from django.db import migrations
from datetime import datetime, timedelta

def update_durations(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    Booking = apps.get_model('bookings', 'Booking')

    # Update Services
    Service.objects.filter(duration_minutes=60).update(duration_minutes=30)
    Service.objects.filter(duration_minutes=90).update(duration_minutes=45)

    # Update Bookings
    # We only update bookings that match the durations we are changing
    for booking in Booking.objects.filter(duration_minutes__in=[60, 90]):
        try:
            if booking.duration_minutes == 60:
                booking.duration_minutes = 30
                new_duration = 30
            else:
                booking.duration_minutes = 45
                new_duration = 45

            # Recalculate end_time
            if booking.booking_date and booking.start_time:
                start_dt = datetime.combine(booking.booking_date, booking.start_time)
                booking.end_time = (start_dt + timedelta(minutes=new_duration)).time()
                # Ensure updated_at is refreshed despite update_fields
                booking.save(update_fields=['duration_minutes', 'end_time'])
        except (AttributeError, TypeError):
            continue

def reverse_durations(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    Booking = apps.get_model('bookings', 'Booking')

    # Reverse Services
    Service.objects.filter(duration_minutes=30).update(duration_minutes=60)
    Service.objects.filter(duration_minutes=45).update(duration_minutes=90)

    # Reverse Bookings
    for booking in Booking.objects.filter(duration_minutes__in=[30, 45]):
        try:
            if booking.duration_minutes == 30:
                booking.duration_minutes = 60
                new_duration = 60
            else:
                booking.duration_minutes = 90
                new_duration = 90

            if booking.booking_date and booking.start_time:
                start_dt = datetime.combine(booking.booking_date, booking.start_time)
                booking.end_time = (start_dt + timedelta(minutes=new_duration)).time()
                booking.save(update_fields=['duration_minutes', 'end_time'])
        except (AttributeError, TypeError):
            continue

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_alter_service_duration_minutes'),
        ('bookings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(update_durations, reverse_durations),
    ]
