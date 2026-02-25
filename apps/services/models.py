"""
Service model — each row is a unique service+duration combination.

Design decision: each duration variant is a SEPARATE Service row.
Example:
  - "Swedish Massage 30 min"  price=₹1200  duration=30
  - "Swedish Massage 45 min"  price=₹1700  duration=45

This keeps slot generation simple and pricing self-contained.
A service can be offered at MULTIPLE branches via the ManyToManyField.
"""
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import BaseModel
from apps.branches.models import Branch


class Service(BaseModel):
    # ManyToMany: one service can be offered at multiple branches
    branches = models.ManyToManyField(
        Branch,
        related_name='services',
        blank=True,
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(30)],
        help_text='Session duration in minutes (30 or 45)',
    )
    buffer_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Buffer/cleanup gap after session (hidden from guest)',
    )
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    benefits = models.TextField(
        blank=True,
        help_text='Key benefits of this service, separated by newlines.'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ['name', 'duration_minutes']

    def __str__(self):
        branch_names = ', '.join(b.name for b in self.branches.all()) or 'No Branch'
        return f"{self.name} ({self.duration_minutes} min) — {branch_names}"

    @property
    def total_block_minutes(self):
        """Total time block a booking occupies including buffer."""
        return self.duration_minutes + self.buffer_minutes

    @property
    def deposit_price(self):
        """10% deposit price required for booking."""
        from decimal import Decimal
        return (self.price * Decimal('0.10')).quantize(Decimal('0.01'))
