from django.contrib import admin
from .models import DashboardConfig

@admin.register(DashboardConfig)
class DashboardConfigAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not DashboardConfig.objects.exists()
