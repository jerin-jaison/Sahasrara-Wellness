from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'razorpay_order_id', 'booking', 'amount', 'currency', 'status', 'paid_at', 'created_at'
    ]
    list_filter = ['status', 'currency']
    search_fields = ['razorpay_order_id', 'razorpay_payment_id', 'booking__guest__name']
    readonly_fields = [
        'id', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature',
        'webhook_event_id', 'webhook_payload', 'paid_at', 'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Payment', {'fields': ('id', 'booking', 'amount', 'currency', 'status', 'paid_at')}),
        ('Razorpay IDs', {'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')}),
        ('Webhook', {'fields': ('webhook_event_id', 'webhook_payload'), 'classes': ('collapse',)}),
        ('Audit', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
