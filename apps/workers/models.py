"""
Worker models: Worker profile, WorkerSchedule, WorkerLeave.
Each worker belongs to exactly one branch.
"""
from django.db import models
from apps.core.models import BaseModel, UUIDModel, TimestampedModel
from apps.branches.models import Branch


class Worker(BaseModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='workers',
    )
    name = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=255, blank=True, help_text="Where the therapist operates (e.g. Home Service, South Mumbai)")
    is_active = models.BooleanField(default=True, db_index=True)

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else ""

    class Meta:
        verbose_name = 'Worker'
        verbose_name_plural = 'Workers'
        ordering = ['branch', 'name']

    def __str__(self):
        return f"{self.name} — {self.branch.name}"




class WorkerSchedule(UUIDModel):
    """
    Defines a worker's working hours for a given weekday.
    A worker can have multiple schedule rows (one per working day).
    """
    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name = 'Worker Schedule'
        verbose_name_plural = 'Worker Schedules'
        unique_together = [('worker', 'weekday')]
        ordering = ['worker', 'weekday']

    def __str__(self):
        return (
            f"{self.worker.name} — {self.get_weekday_display()} "
            f"({self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')})"
        )


class WorkerLeave(UUIDModel, TimestampedModel):
    """Marks a specific calendar date as a leave day for a worker."""
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='leaves',
    )
    leave_date = models.DateField(db_index=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Worker Leave'
        verbose_name_plural = 'Worker Leaves'
        unique_together = [('worker', 'leave_date')]
        ordering = ['-leave_date']

    def __str__(self):
        return f"{self.worker.name} — Leave on {self.leave_date}"
