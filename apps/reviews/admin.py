from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'is_published', 'sort_order', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('client_name', 'instagram_url')
    ordering = ('sort_order', '-created_at')
