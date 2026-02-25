from django.db import migrations
from datetime import datetime, timedelta

def update_durations(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    Booking = apps.get_model('bookings', 'Booking')

    # Update Services
    Service.objects.filter(duration_minutes=60).update(duration_minutes=30)
    Service.objects.filter(duration_minutes=90).update(duration_minutes=45)

    # Update Bookings
    for booking in Booking.objects.all():
        if booking.duration_minutes == 60:
            booking.duration_minutes = 30
            # Recalculate end_time
            start_dt = datetime.combine(booking.booking_date, booking.start_time)
            booking.end_time = (start_dt + timedelta(minutes=30)).time()
            booking.save(update_fields=['duration_minutes', 'end_time'])
        elif booking.duration_minutes == 90:
            booking.duration_minutes = 45
            # Recalculate end_time
            start_dt = datetime.combine(booking.booking_date, booking.start_time)
            booking.end_time = (start_dt + timedelta(minutes=45)).time()
            booking.save(update_fields=['duration_minutes', 'end_time'])

def reverse_durations(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    Booking = apps.get_model('bookings', 'Booking')

    # Reverse Services
    Service.objects.filter(duration_minutes=30).update(duration_minutes=60)
    Service.objects.filter(duration_minutes=45).update(duration_minutes=90)

    # Reverse Bookings
    for booking in Booking.objects.all():
        if booking.duration_minutes == 30:
            booking.duration_minutes = 60
            start_dt = datetime.combine(booking.booking_date, booking.start_time)
            booking.end_time = (start_dt + timedelta(minutes=60)).time()
            booking.save(update_fields=['duration_minutes', 'end_time'])
        elif booking.duration_minutes == 45:
            booking.duration_minutes = 90
            start_dt = datetime.combine(booking.booking_date, booking.start_time)
            booking.end_time = (start_dt + timedelta(minutes=90)).time()
            booking.save(update_fields=['duration_minutes', 'end_time'])

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_alter_service_duration_minutes'),
        ('bookings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(update_durations, reverse_durations),
    ]
