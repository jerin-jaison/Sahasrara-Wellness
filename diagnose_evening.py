import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sahasrara.settings.development')
django.setup()

from apps.branches.models import Branch
from apps.workers.models import Worker, WorkerSchedule
from apps.services.models import Service
from apps.bookings.engine import get_availability_window, get_available_slots

def diagnose_evening_slots():
    # Feb 25, 2026 is a Wednesday (Weekday 2)
    test_date = date(2026, 2, 25)
    branch = Branch.objects.first()
    worker = Worker.objects.get(name="Rajan Kumar")
    service = Service.objects.filter(name="Deep Tissue Massage").first()

    print(f"Branch: {branch.name}")
    print(f"Branch Daily Hours: {branch.opening_time} - {branch.closing_time}")
    
    if service:
        print(f"Service: {service.name} | Duration: {service.duration_minutes} | Buffer: {service.buffer_minutes}")
    else:
        print("Service 'Deep Tissue Massage' not found.")
        return

    sched = WorkerSchedule.objects.filter(worker=worker, weekday=test_date.weekday()).first()
    if sched:
        print(f"Worker Schedule for Wednesday: {sched.start_time} - {sched.end_time}")
    else:
        print("Worker has no specific schedule for Wednesday (using fallback).")

    window = get_availability_window(branch, worker, test_date)
    print(f"Engine Availability Window: {window}")

    slots = get_available_slots(worker, service, test_date)
    print(f"Generated {len(slots)} slots:")
    for slot in slots:
        print(f"  {slot['display']}")

if __name__ == "__main__":
    diagnose_evening_slots()
