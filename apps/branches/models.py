"""
Branch model — represents a physical massage center location.
"""
from datetime import time
from django.db import models
from apps.core.models import BaseModel


class Branch(BaseModel):
    name = models.CharField(max_length=120)
    address = models.TextField()
    city = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    google_maps_url = models.URLField(blank=True)
    
    # Working Hours
    opening_time = models.TimeField(default=time(10, 0))
    closing_time = models.TimeField(default=time(19, 0))
    
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.city})"

    def get_working_days(self):
        """Returns a list of integer weekdays (0-6) where the branch is open."""
        return list(self.schedules.filter(is_open=True).values_list('weekday', flat=True))


class BranchSchedule(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='schedules')
    weekday = models.IntegerField(choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ])
    is_open = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'weekday')
        ordering = ['weekday']

    def __str__(self):
        return f"{self.branch.name} - {self.get_weekday_display()}: {'Open' if self.is_open else 'Closed'}"
