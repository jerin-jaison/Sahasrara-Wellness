"""
Seed management command.

Populates the database with initial demo data:
  - 2 branches
  - 4 workers (2 per branch) with weekly schedules
  - 8 services (4 per branch, 2 x 30-min, 2 x 45-min variants)

Usage:
    python manage.py seed_data
    python manage.py seed_data --flush   # wipe and re-seed
"""
from django.core.management.base import BaseCommand
from apps.branches.models import Branch
from apps.services.models import Service
from apps.workers.models import Worker, WorkerSchedule
from datetime import time


class Command(BaseCommand):
    help = 'Seed initial branches, workers, schedules, and services'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete all existing seed data before creating fresh records',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('Flushing existing data...')
            WorkerSchedule.objects.all().delete()
            Worker.all_objects.all().hard_delete()
            Service.all_objects.all().hard_delete()
            Branch.all_objects.all().hard_delete()

        self.stdout.write('Seeding branches...')
        branch1, _ = Branch.objects.get_or_create(
            name='Sahasrara Wellness — Koramangala',
            defaults={
                'address': '123, 5th Block, Koramangala, Bengaluru',
                'city': 'Bengaluru',
                'phone': '+91 98765 43210',
                'email': 'koramangala@sahasrarawellness.com',
            }
        )
        branch2, _ = Branch.objects.get_or_create(
            name='Sahasrara Wellness — Indiranagar',
            defaults={
                'address': '456, 100 Feet Road, Indiranagar, Bengaluru',
                'city': 'Bengaluru',
                'phone': '+91 98765 43211',
                'email': 'indiranagar@sahasrarawellness.com',
            }
        )
        self.stdout.write(self.style.SUCCESS('  ✔ 2 branches created'))

        # ── Services ──────────────────────────────────────────────────────────
        self.stdout.write('Seeding services...')
        services_data = [
            # Branch 1 services
            {'branch': branch1, 'name': 'Swedish Massage', 'duration_minutes': 30,  'price': 1200, 'description': 'A classic relaxation massage using long smooth strokes to ease tension and improve circulation.'},
            {'branch': branch1, 'name': 'Swedish Massage', 'duration_minutes': 45,  'price': 1700, 'description': 'A classic relaxation massage using long smooth strokes to ease tension and improve circulation.'},
            {'branch': branch1, 'name': 'Deep Tissue Massage', 'duration_minutes': 30, 'price': 1400, 'description': 'Targets deeper layers of muscle and connective tissue to relieve chronic pain and tension.'},
            {'branch': branch1, 'name': 'Deep Tissue Massage', 'duration_minutes': 45, 'price': 1900, 'description': 'Targets deeper layers of muscle and connective tissue to relieve chronic pain and tension.'},
            # Branch 2 services
            {'branch': branch2, 'name': 'Swedish Massage', 'duration_minutes': 30,  'price': 1200, 'description': 'A classic relaxation massage using long smooth strokes to ease tension and improve circulation.'},
            {'branch': branch2, 'name': 'Swedish Massage', 'duration_minutes': 45,  'price': 1700, 'description': 'A classic relaxation massage using long smooth strokes to ease tension and improve circulation.'},
            {'branch': branch2, 'name': 'Aromatherapy Massage', 'duration_minutes': 30, 'price': 1350, 'description': 'Combines the benefits of massage with the healing properties of essential oils for deep relaxation.'},
            {'branch': branch2, 'name': 'Aromatherapy Massage', 'duration_minutes': 45, 'price': 1850, 'description': 'Combines the benefits of massage with the healing properties of essential oils for deep relaxation.'},
        ]
        for svc in services_data:
            Service.objects.get_or_create(
                branch=svc['branch'], name=svc['name'], duration_minutes=svc['duration_minutes'],
                defaults={'price': svc['price'], 'description': svc['description'], 'buffer_minutes': 0}
            )
        self.stdout.write(self.style.SUCCESS('  ✔ 8 services created'))

        # ── Workers ───────────────────────────────────────────────────────────
        self.stdout.write('Seeding workers...')
        workers_data = [
            {'branch': branch1, 'name': 'Priya Nair',    'bio': 'Certified therapist with 5 years of experience in Swedish and deep tissue massage.'},
            {'branch': branch1, 'name': 'Rajan Kumar',   'bio': 'Sports massage specialist focused on muscle recovery and injury prevention.'},
            {'branch': branch2, 'name': 'Anitha Raj',    'bio': 'Aromatherapy expert trained in holistic wellness practices from Kerala.'},
            {'branch': branch2, 'name': 'Suresh Menon',  'bio': 'Relaxation specialist with a calm technique ideal for stress relief sessions.'},
        ]
        created_workers = []
        for w in workers_data:
            worker, _ = Worker.objects.get_or_create(
                name=w['name'], branch=w['branch'],
                defaults={'bio': w['bio']}
            )
            created_workers.append(worker)
        self.stdout.write(self.style.SUCCESS('  ✔ 4 workers created'))

        # ── Worker Schedules (Mon–Sat, 10:00–19:00) ───────────────────────────
        self.stdout.write('Seeding worker schedules...')
        working_days = [0, 1, 2, 3, 4, 5]  # Monday to Saturday
        for worker in created_workers:
            for day in working_days:
                WorkerSchedule.objects.get_or_create(
                    worker=worker, weekday=day,
                    defaults={'start_time': time(10, 0), 'end_time': time(19, 0)}
                )
        self.stdout.write(self.style.SUCCESS('  ✔ Worker schedules set (Mon–Sat, 10:00–19:00)'))

        self.stdout.write(self.style.SUCCESS('\n✅ Seed complete! 2 branches, 4 workers, 8 services ready.'))
