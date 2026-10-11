from django.contrib import admin
from .models import Report, Block

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reason', 'reporter', 'reported_user', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'reason', 'created_at')
    search_fields = ('reporter__username', 'reported_user__username', 'details')
    list_editable = ('is_resolved',)
    readonly_fields = ('created_at',)

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')
    search_fields = ('blocker__username', 'blocked__username')
