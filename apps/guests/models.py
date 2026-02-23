"""
Guest model — represents a booking customer without a user account.
Phone number is the canonical identity key.

Phone normalisation guarantees deduplication regardless of how the
guest types their number:
  +91 98765 43210  →  9876543210
  091-9876543210   →  9876543210
  09876543210      →  9876543210
  9876543210       →  9876543210  (already clean)
"""
import re
from django.db import models
from apps.core.models import UUIDModel, TimestampedModel


def normalize_phone(raw: str) -> str:
    """
    Normalise an Indian mobile number to exactly 10 digits.

    Steps:
      1. Strip all non-digit characters (spaces, dashes, +, parentheses)
      2. Remove leading country code 91 if the result is 12 digits
      3. Remove leading 0 if the result is 11 digits
      4. Validate final length is 10

    Raises ValueError if the result is not 10 digits.
    """
    digits = re.sub(r'\D', '', raw)           # keep digits only

    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]                    # strip country code
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]                    # strip STD trunk prefix

    if len(digits) != 10:
        raise ValueError(
            f"Cannot normalise phone number '{raw}' — "
            f"expected 10 digits after normalisation, got {len(digits)}."
        )
    return digits


class Guest(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)

    class Meta:
        verbose_name = 'Guest'
        verbose_name_plural = 'Guests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @classmethod
    def get_or_create_by_phone(cls, name, phone, email=''):
        """
        Canonical guest lookup: always deduplicate by normalised phone.
        Normalises phone to 10-digit Indian format before lookup.
        Updates name and email on subsequent bookings by the same guest.

        Raises ValueError if phone cannot be normalised.
        """
        phone = normalize_phone(phone)
        guest, created = cls.objects.get_or_create(
            phone=phone,
            defaults={'name': name, 'email': email},
        )
        if not created:
            # Keep most-recent name and email
            update_fields = []
            if name and guest.name != name:
                guest.name = name
                update_fields.append('name')
            if email and guest.email != email:
                guest.email = email
                update_fields.append('email')
            if update_fields:
                guest.save(update_fields=update_fields)
        return guest, created
