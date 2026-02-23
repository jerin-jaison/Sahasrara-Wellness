from django.contrib import admin
from .models import Worker, WorkerSchedule, WorkerLeave


class WorkerScheduleInline(admin.TabularInline):
    model = WorkerSchedule
    extra = 1


class WorkerLeaveInline(admin.TabularInline):
    model = WorkerLeave
    extra = 0


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ['name', 'branch', 'years_experience', 'phone', 'is_active', 'deleted_at']
    list_filter = ['branch', 'is_active']
    search_fields = ['name', 'branch__name', 'phone']
    list_editable = ['is_active']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    inlines = [WorkerScheduleInline, WorkerLeaveInline]
    fieldsets = (
        ('Worker Info', {'fields': ('id', 'branch', 'name', 'photo', 'bio', 'years_experience', 'phone')}),
        ('Status', {'fields': ('is_active',)}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'deleted_at'), 'classes': ('collapse',)}),
    )


@admin.register(WorkerSchedule)
class WorkerScheduleAdmin(admin.ModelAdmin):
    list_display = ['worker', 'weekday', 'start_time', 'end_time']
    list_filter = ['worker__branch', 'weekday']
    search_fields = ['worker__name']


@admin.register(WorkerLeave)
class WorkerLeaveAdmin(admin.ModelAdmin):
    list_display = ['worker', 'leave_date', 'reason']
    list_filter = ['worker__branch', 'leave_date']
    search_fields = ['worker__name']
    date_hierarchy = 'leave_date'
