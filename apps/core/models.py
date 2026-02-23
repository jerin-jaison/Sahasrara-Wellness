"""
Core base model mixins.
All production models should inherit from these.
"""
import uuid
from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    """Primary key is a UUID, not an auto-incrementing integer."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Automatically tracks creation and last-update timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """Custom queryset that excludes soft-deleted records by default."""
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Soft-delete mixin. Records are never physically deleted.
    Use .delete() to soft-delete, .hard_delete() to permanently remove.
    Default manager excludes soft-deleted records automatically.
    """
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Bypass soft-delete filter when needed

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class BaseModel(UUIDModel, TimestampedModel, SoftDeleteModel):
    """
    Convenience base combining UUID pk + timestamps + soft delete.
    Use this for all main business models.
    """
    class Meta:
        abstract = True
