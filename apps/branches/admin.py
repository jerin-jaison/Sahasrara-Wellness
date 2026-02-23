from django.contrib import admin
from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'phone', 'is_active', 'deleted_at']
    list_filter = ['is_active', 'city']
    search_fields = ['name', 'city', 'phone']
    list_editable = ['is_active']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    fieldsets = (
        ('Branch Info', {'fields': ('id', 'name', 'address', 'city', 'phone', 'email', 'google_maps_url')}),
        ('Status', {'fields': ('is_active',)}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'deleted_at'), 'classes': ('collapse',)}),
    )
