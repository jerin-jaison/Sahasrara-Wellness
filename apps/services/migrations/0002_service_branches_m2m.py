"""
Migration: Replace Service.branch (ForeignKey) with Service.branches (ManyToManyField).

Steps:
  1. Make the existing branch FK nullable (so we can operate without it)
  2. Add the new M2M 'branches' field (creates services_service_branches table)
  3. Copy each service's branch_id into the M2M through table
  4. Remove the old 'branch' FK column
"""
import django.db.models.deletion
import uuid
from django.db import migrations, models


def copy_fk_to_m2m(apps, schema_editor):
    """Copy existing branch FK → branches M2M for every Service row."""
    Service = apps.get_model('services', 'Service')
    for service in Service.objects.all():
        if service.branch_id:
            service.branches.add(service.branch_id)


def reverse_m2m_to_fk(apps, schema_editor):
    """Reverse: copy first branch back into the FK column (best-effort)."""
    Service = apps.get_model('services', 'Service')
    for service in Service.objects.all():
        first = service.branches.first()
        if first:
            service.branch_id = first.pk
            service.save(update_fields=['branch_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('branches', '0001_initial'),
        ('services', '0001_initial'),
    ]

    operations = [
        # Step 1 — Make old FK nullable so data migration can work safely
        migrations.AlterField(
            model_name='service',
            name='branch',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='services_old',
                to='branches.branch',
            ),
        ),

        # Step 2 — Add the new M2M field
        migrations.AddField(
            model_name='service',
            name='branches',
            field=models.ManyToManyField(
                blank=True,
                related_name='services',
                to='branches.branch',
            ),
        ),

        # Step 3 — Copy data: branch FK → branches M2M
        migrations.RunPython(copy_fk_to_m2m, reverse_code=reverse_m2m_to_fk),

        # Step 4 — Remove the old FK column
        migrations.RemoveField(
            model_name='service',
            name='branch',
        ),

        # Step 5 — Fix ordering (can't ORDER BY M2M columns)
        migrations.AlterModelOptions(
            name='service',
            options={
                'verbose_name': 'Service',
                'verbose_name_plural': 'Services',
                'ordering': ['name', 'duration_minutes'],
            },
        ),
    ]
