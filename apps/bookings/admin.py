from django.contrib import admin
from .models import Booking, SlotLock, BookingStatusLog


class BookingStatusLogInline(admin.TabularInline):
    model = BookingStatusLog
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'changed_by', 'reason', 'changed_at']
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'short_id', 'guest', 'branch', 'service', 'worker',
        'booking_date', 'start_time', 'status', 'payment_status', 'amount_paid', 'is_manual'
    ]
    list_filter = ['status', 'payment_status', 'branch', 'is_manual', 'booking_date']
    search_fields = ['guest__name', 'guest__phone', 'worker__name', 'service__name']
    readonly_fields = ['id', 'access_token', 'created_at', 'updated_at', 'deleted_at']
    date_hierarchy = 'booking_date'
    inlines = [BookingStatusLogInline]
    fieldsets = (
        ('Booking', {'fields': ('id', 'branch', 'service', 'worker', 'guest', 'slot_lock')}),
        ('Schedule', {'fields': ('booking_date', 'start_time', 'end_time', 'duration_minutes')}),
        ('Status', {'fields': ('status', 'payment_status', 'amount_paid', 'is_manual', 'notes')}),
        ('Access', {'fields': ('access_token',)}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'deleted_at'), 'classes': ('collapse',)}),
    )

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'


@admin.register(SlotLock)
class SlotLockAdmin(admin.ModelAdmin):
    list_display = ['worker', 'branch', 'booking_date', 'start_time', 'end_time', 'released', 'expires_at']
    list_filter = ['released', 'branch']
    readonly_fields = ['id', 'created_at', 'updated_at']
    search_fields = ['worker__name', 'session_key']


@admin.register(BookingStatusLog)
class BookingStatusLogAdmin(admin.ModelAdmin):
    list_display = ['booking', 'from_status', 'to_status', 'changed_by', 'changed_at']
    readonly_fields = ['id', 'booking', 'from_status', 'to_status', 'changed_by', 'reason', 'changed_at']
    search_fields = ['booking__guest__name']
