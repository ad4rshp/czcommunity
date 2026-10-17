from django.contrib import admin
from .models import DashboardConfig
from .admin_dashboard import get_admin_dashboard_context, handle_admin_dashboard_action

@admin.register(DashboardConfig)
class DashboardConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_maintenance_mode', 'show_beta_warning', 'show_announcement')
    fieldsets = (
        ("Site Operational State", {
            'fields': ('is_maintenance_mode', 'maintenance_message', 'show_beta_warning')
        }),
        ("Global Announcement Banner", {
            'fields': ('show_announcement', 'announcement_title', 'announcement_content')
        }),
        ("Community Guidelines & Rules", {
            'fields': ('show_rules', 'rules_text', 'welcome_message', 'show_quick_actions')
        }),
    )

    def has_add_permission(self, request):
        return not DashboardConfig.objects.exists()

# Enhance Django admin index with rich dashboard telemetry and action handlers
_original_admin_index = admin.site.index

def enhanced_admin_index(request, extra_context=None):
    if request.method == 'POST' and request.user.is_staff:
        return handle_admin_dashboard_action(request)
        
    extra = extra_context or {}
    try:
        if request.user.is_staff:
            extra.update(get_admin_dashboard_context())
    except Exception as e:
        import traceback
        traceback.print_exc()
        
    return _original_admin_index(request, extra_context=extra)

admin.site.index = enhanced_admin_index

