from django.contrib import admin
from .models import Service


def get_branches(obj):
    return ', '.join(b.name for b in obj.branches.all()) or '—'
get_branches.short_description = 'Branches'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', get_branches, 'duration_minutes', 'price', 'buffer_minutes', 'is_active']
    list_filter = ['branches', 'is_active']
    search_fields = ['name', 'branches__name']
    list_editable = ['is_active', 'price']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    fieldsets = (
        ('Service Info', {'fields': ('id', 'branches', 'name', 'description', 'benefits', 'image')}),
        ('Timing & Pricing', {'fields': ('duration_minutes', 'buffer_minutes', 'price')}),
        ('Status', {'fields': ('is_active',)}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'deleted_at'), 'classes': ('collapse',)}),
    )
