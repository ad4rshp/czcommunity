import platform
import django
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import redirect
from django.utils import timezone
from accounts.models import Report, Block
from chat.models import Community, Channel, Message, DirectMessage, AuditLog
from core.models import DashboardConfig
from profiles.models import Profile

def get_admin_dashboard_context():
    """Gathers real-time telemetry, moderation status, and KPIs for admin dashboard."""
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    banned_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()
    
    total_communities = Community.objects.count()
    total_channels = Channel.objects.count()
    total_messages = Message.objects.count()
    total_dms = DirectMessage.objects.count()
    
    pending_reports = Report.objects.filter(is_resolved=False).select_related('reporter', 'reported_user').order_by('-created_at')[:15]
    pending_reports_count = Report.objects.filter(is_resolved=False).count()
    
    recent_users = User.objects.select_related('profile').order_by('-date_joined')[:8]
    recent_communities = Community.objects.select_related('owner').annotate(
        members_count=Count('members', distinct=True),
        channels_count=Count('categories__channels', distinct=True)
    ).order_by('-created_at')[:8]
    
    recent_audit_logs = AuditLog.objects.select_related('user', 'community').order_by('-created_at')[:10]
    site_config = DashboardConfig.load()
    
    system_info = {
        'python_version': platform.python_version(),
        'django_version': django.get_version(),
        'os_info': f"{platform.system()} {platform.release()}",
        'db_engine': django.db.connection.settings_dict.get('ENGINE', '').split('.')[-1],
        'debug_mode': django.conf.settings.DEBUG,
    }
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'banned_users': banned_users,
        'staff_users': staff_users,
        'total_communities': total_communities,
        'total_channels': total_channels,
        'total_messages': total_messages + total_dms,
        'total_channel_messages': total_messages,
        'total_dms': total_dms,
        'pending_reports': pending_reports,
        'pending_reports_count': pending_reports_count,
        'recent_users': recent_users,
        'recent_communities': recent_communities,
        'recent_audit_logs': recent_audit_logs,
        'site_config': site_config,
        'system_info': system_info,
    }

def handle_admin_dashboard_action(request):
    """Processes quick admin actions directly from the dashboard."""
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('admin:index')
        
    action_type = request.POST.get('action_type')
    
    if action_type == 'toggle_maintenance':
        config = DashboardConfig.load()
        config.is_maintenance_mode = not config.is_maintenance_mode
        config.save()
        status_text = "ENABLED (Site in Maintenance Mode)" if config.is_maintenance_mode else "DISABLED (Site is LIVE)"
        messages.success(request, f"Maintenance Mode is now {status_text}.")
        
    elif action_type == 'toggle_beta':
        config = DashboardConfig.load()
        config.show_beta_warning = not config.show_beta_warning
        config.save()
        status_text = "VISIBLE" if config.show_beta_warning else "HIDDEN"
        messages.success(request, f"Beta badge on landing page is now {status_text}.")

    elif action_type == 'update_announcement':
        config = DashboardConfig.load()
        config.announcement_title = request.POST.get('announcement_title', config.announcement_title)
        config.announcement_content = request.POST.get('announcement_content', config.announcement_content)
        config.show_announcement = request.POST.get('show_announcement') == 'on'
        config.save()
        messages.success(request, "Global site announcement updated successfully.")

    elif action_type == 'resolve_report':
        report_id = request.POST.get('report_id')
        try:
            report = Report.objects.get(id=report_id)
            report.is_resolved = True
            report.save()
            messages.success(request, f"Report #{report.id} ({report.reason}) marked as RESOLVED.")
        except Report.DoesNotExist:
            messages.error(request, f"Report #{report_id} not found.")

    elif action_type == 'ban_user':
        user_id = request.POST.get('user_id')
        try:
            target = User.objects.get(id=user_id)
            if target.is_superuser:
                messages.error(request, "Cannot ban a superuser account.")
            else:
                target.is_active = False
                target.save()
                messages.warning(request, f"User '{target.username}' has been BANNED / SUSPENDED.")
        except User.DoesNotExist:
            messages.error(request, f"User #{user_id} not found.")

    elif action_type == 'unban_user':
        user_id = request.POST.get('user_id')
        try:
            target = User.objects.get(id=user_id)
            target.is_active = True
            target.save()
            messages.success(request, f"User '{target.username}' has been RESTORED (Active).")
        except User.DoesNotExist:
            messages.error(request, f"User #{user_id} not found.")

    elif action_type == 'delete_message':
        msg_id = request.POST.get('message_id')
        try:
            msg = Message.objects.get(id=msg_id)
            channel_name = msg.channel.name
            msg.delete()
            messages.success(request, f"Message #{msg_id} in #{channel_name} was PERMANENTLY DELETED.")
        except Message.DoesNotExist:
            messages.error(request, f"Message #{msg_id} not found.")

    return redirect('admin:index')
