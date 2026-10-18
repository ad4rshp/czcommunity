import platform
import secrets
import django
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib import admin
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from accounts.models import Report, Block
from chat.models import Community, Channel, Message, DirectMessage, AuditLog
from core.models import DashboardConfig
from profiles.models import Profile


MODEL_GROUPS = (
    ('platform', 'Platform', {'core'}),
    ('communities', 'Communities & chat', {'chat', 'bots'}),
    ('members', 'Members & social', {'auth', 'profiles'}),
    ('safety', 'Safety & moderation', {'accounts'}),
)


def _page_numbers(page_obj, radius=2):
    start = max(1, page_obj.number - radius)
    stop = min(page_obj.paginator.num_pages, page_obj.number + radius)
    return range(start, stop + 1)


def _model_registry(request, query, selected_group, per_page=12):
    app_list = admin.site.get_app_list(request) if request else []
    entries = []
    group_options = []

    for position, (group_key, group_label, app_labels) in enumerate(MODEL_GROUPS):
        group_entries = []
        for app in app_list:
            if app.get('app_label') not in app_labels:
                continue
            for model in app.get('models', []):
                entry = {
                    **model,
                    'app_name': app.get('name', ''),
                    'app_label': app.get('app_label', ''),
                    'group_key': group_key,
                    'group_label': group_label,
                    'group_position': position,
                }
                search_text = f"{entry['name']} {entry['app_name']} {entry['app_label']}"
                if query and query.casefold() not in search_text.casefold():
                    continue
                group_entries.append(entry)
        if group_entries:
            group_options.append({'key': group_key, 'name': group_label})
            entries.extend(group_entries)

    valid_groups = {option['key'] for option in group_options}
    selected_group = selected_group if selected_group in valid_groups else ''
    if selected_group:
        entries = [entry for entry in entries if entry['group_key'] == selected_group]
    entries.sort(key=lambda entry: (entry['group_position'], entry['app_name'], entry['name']))
    return Paginator(entries, per_page), group_options, selected_group

def get_admin_dashboard_context(request=None):
    """Gathers real-time telemetry, moderation status, and scalable paginated records for admin dashboard."""
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    banned_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()
    
    total_communities = Community.objects.count()
    total_channels = Channel.objects.count()
    total_messages = Message.objects.count()
    total_dms = DirectMessage.objects.count()
    
    # Reports
    pending_reports = Report.objects.filter(is_resolved=False).select_related('reporter', 'reported_user').order_by('-created_at')[:15]
    pending_reports_count = Report.objects.filter(is_resolved=False).count()
    
    # All communities for selection
    all_communities = Community.objects.only('id', 'name', 'slug', 'is_verified').order_by('name')
    
    # Searchable, status-filtered, paginated user directory.
    user_q = request.GET.get('user_q', '').strip() if request else ''
    user_status = request.GET.get('user_status', 'all') if request else 'all'
    if user_status not in {'all', 'active', 'suspended', 'staff', 'superuser'}:
        user_status = 'all'
    user_qs = User.objects.select_related('profile')
    if user_q:
        user_qs = user_qs.filter(
            Q(username__icontains=user_q) |
            Q(email__icontains=user_q) |
            Q(profile__unique_id__icontains=user_q)
        )
    if user_status == 'active':
        user_qs = user_qs.filter(is_active=True, is_superuser=False)
    elif user_status == 'suspended':
        user_qs = user_qs.filter(is_active=False)
    elif user_status == 'staff':
        user_qs = user_qs.filter(is_staff=True)
    elif user_status == 'superuser':
        user_qs = user_qs.filter(is_superuser=True)
    user_qs = user_qs.order_by('-date_joined')
    user_paginator = Paginator(user_qs, 10)
    user_page = request.GET.get('user_page', 1) if request else 1
    users_page_obj = user_paginator.get_page(user_page)
    
    # Searchable, status-filtered, paginated community directory.
    comm_q = request.GET.get('comm_q', '').strip() if request else ''
    comm_status = request.GET.get('comm_status', 'all') if request else 'all'
    if comm_status not in {'all', 'verified', 'standard'}:
        comm_status = 'all'
    comm_qs = Community.objects.select_related('owner').annotate(
        members_count=Count('members', distinct=True),
        channels_count=Count('categories__channels', distinct=True)
    )
    if comm_q:
        comm_qs = comm_qs.filter(Q(name__icontains=comm_q) | Q(slug__icontains=comm_q) | Q(owner__username__icontains=comm_q))
    if comm_status == 'verified':
        comm_qs = comm_qs.filter(is_verified=True)
    elif comm_status == 'standard':
        comm_qs = comm_qs.filter(is_verified=False)
    comm_qs = comm_qs.order_by('-created_at')
    comm_paginator = Paginator(comm_qs, 10)
    comm_page = request.GET.get('comm_page', 1) if request else 1
    comm_page_obj = comm_paginator.get_page(comm_page)
    
    # Message Monitoring: Channel Messages Query & Filter
    msg_q = request.GET.get('msg_q', '').strip() if request else ''
    msg_type = request.GET.get('msg_type', 'all') if request else 'all'
    if msg_type not in {'all', 'channel', 'dm'}:
        msg_type = 'all'
    msg_comm_id = request.GET.get('msg_comm', '') if request else ''
    if msg_type == 'dm' or (msg_comm_id and not str(msg_comm_id).isdigit()):
        msg_comm_id = ''
    
    msg_qs = Message.objects.select_related(
        'author', 'author__profile', 'channel', 'channel__category__community'
    )
    if msg_q:
        msg_qs = msg_qs.filter(
            Q(content__icontains=msg_q) |
            Q(author__username__icontains=msg_q) |
            Q(author__profile__unique_id__icontains=msg_q) |
            Q(channel__name__icontains=msg_q) |
            Q(channel__category__community__name__icontains=msg_q)
        )
    if msg_comm_id:
        msg_qs = msg_qs.filter(channel__category__community_id=msg_comm_id)
        
    msg_qs = msg_qs.order_by('-created_at')
    if msg_type == 'dm':
        msg_qs = Message.objects.none()
    msg_paginator = Paginator(msg_qs, 12)
    msg_page = request.GET.get('msg_page', 1) if request else 1
    messages_page_obj = msg_paginator.get_page(msg_page)
    
    # Message Monitoring: Direct Messages Query & Filter
    dm_qs = DirectMessage.objects.select_related(
        'author', 'author__profile', 'session__user1__profile', 'session__user2__profile'
    )
    if msg_q:
        dm_qs = dm_qs.filter(
            Q(content__icontains=msg_q) |
            Q(author__username__icontains=msg_q) |
            Q(author__profile__unique_id__icontains=msg_q) |
            Q(session__user1__username__icontains=msg_q) |
            Q(session__user2__username__icontains=msg_q)
        )
    if msg_type == 'channel':
        dm_qs = DirectMessage.objects.none()
    dm_qs = dm_qs.order_by('-created_at')
    dm_paginator = Paginator(dm_qs, 12)
    dm_page = request.GET.get('dm_page', 1) if request else 1
    dms_page_obj = dm_paginator.get_page(dm_page)

    active_tab = request.GET.get('tab', 'overview') if request else 'overview'
    if active_tab not in {'overview', 'messages', 'moderation', 'servers', 'users', 'models'}:
        active_tab = 'overview'

    # Curated, searchable model registry. Technical framework and plugin models
    # stay out of the platform dashboard unless explicitly grouped here.
    model_q = request.GET.get('model_q', '').strip() if request else ''
    requested_model_group = request.GET.get('model_group', '') if request else ''
    if active_tab == 'models':
        model_paginator, model_group_options, model_group = _model_registry(
            request, model_q, requested_model_group
        )
    else:
        model_paginator = Paginator([], 12)
        model_group_options = []
        model_group = ''
    model_page_obj = model_paginator.get_page(request.GET.get('model_page', 1) if request else 1)
    
    # Messages created in last 24h
    last_24h = timezone.now() - timezone.timedelta(hours=24)
    messages_24h_count = Message.objects.filter(created_at__gte=last_24h).count() + DirectMessage.objects.filter(created_at__gte=last_24h).count()
    
    recent_audit_logs = AuditLog.objects.select_related('user', 'community').order_by('-created_at')[:8]
    site_config = DashboardConfig.load()
    
    system_info = {
        'python_version': platform.python_version(),
        'django_version': django.get_version(),
        'os_info': f"{platform.system()} {platform.release()}",
        'db_engine': django.db.connection.settings_dict.get('ENGINE', '').split('.')[-1],
        'debug_mode': django.conf.settings.DEBUG,
        'channel_layer': django.conf.settings.CHANNEL_LAYERS['default']['BACKEND'].rsplit('.', 1)[-1],
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
        'messages_24h_count': messages_24h_count,
        'pending_reports': pending_reports,
        'pending_reports_count': pending_reports_count,
        'all_communities': all_communities,
        'users_page_obj': users_page_obj,
        'user_page_numbers': _page_numbers(users_page_obj),
        'user_q': user_q,
        'user_status': user_status,
        'comm_page_obj': comm_page_obj,
        'comm_page_numbers': _page_numbers(comm_page_obj),
        'comm_q': comm_q,
        'comm_status': comm_status,
        'messages_page_obj': messages_page_obj,
        'message_page_numbers': _page_numbers(messages_page_obj),
        'dms_page_obj': dms_page_obj,
        'dm_page_numbers': _page_numbers(dms_page_obj),
        'msg_q': msg_q,
        'msg_type': msg_type,
        'msg_comm_id': msg_comm_id,
        'model_page_obj': model_page_obj,
        'model_page_numbers': _page_numbers(model_page_obj),
        'model_q': model_q,
        'model_group': model_group,
        'model_group_options': model_group_options,
        'recent_audit_logs': recent_audit_logs,
        'site_config': site_config,
        'system_info': system_info,
        'active_tab': active_tab,
    }

def handle_admin_dashboard_action(request):
    """Processes quick admin actions directly from the dashboard."""
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('admin:index')
        
    action_type = request.POST.get('action_type')
    redirect_tab = request.POST.get('redirect_tab', 'overview')
    admin_base = reverse('admin:index')
    
    if action_type == 'update_official_server':
        config = DashboardConfig.load()
        comm_id = request.POST.get('official_community_id')
        if comm_id:
            try:
                comm = Community.objects.get(id=comm_id)
                config.official_community = comm
                comm.is_verified = True
                comm.save(update_fields=['is_verified'])
                messages.success(request, f"Official Server set to '{comm.name}'.")
            except Community.DoesNotExist:
                config.official_community = None
        else:
            config.official_community = None
            messages.info(request, "Official server unset.")
            
        config.official_invite_link = request.POST.get('official_invite_link', '').strip()
        config.save()
        messages.success(request, "Official server onboarding & invite settings saved.")
        return redirect(f"{admin_base}?tab=overview")
    
    elif action_type == 'toggle_maintenance':
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

    elif action_type == 'update_platform_content':
        config = DashboardConfig.load()
        config.maintenance_message = request.POST.get(
            'maintenance_message', config.maintenance_message
        ).strip()
        config.welcome_message = request.POST.get(
            'welcome_message', config.welcome_message
        ).strip()
        config.rules_text = request.POST.get('rules_text', config.rules_text).strip()
        config.show_rules = request.POST.get('show_rules') == 'on'
        config.show_quick_actions = request.POST.get('show_quick_actions') == 'on'
        config.save()
        messages.success(request, "Platform content and community defaults saved.")

    elif action_type == 'resolve_report':
        report_id = request.POST.get('report_id')
        try:
            report = Report.objects.get(id=report_id)
            report.is_resolved = True
            report.save()
            messages.success(request, f"Report #{report.id} ({report.reason}) marked as RESOLVED.")
        except Report.DoesNotExist:
            messages.error(request, f"Report #{report_id} not found.")
        return redirect(f"{admin_base}?tab=moderation")

    elif action_type == 'ban_user':
        user_identifier = request.POST.get('user_identifier') or request.POST.get('user_id')
        if not user_identifier:
            messages.error(request, "Please enter a username or User ID to ban.")
            return redirect(f"{admin_base}?tab={redirect_tab}")
            
        target = None
        ident_str = str(user_identifier).strip()
        if ident_str.isdigit():
            target = User.objects.filter(id=int(ident_str)).first()
        if not target:
            target = User.objects.filter(
                Q(username__iexact=ident_str) |
                Q(profile__unique_id__iexact=ident_str) |
                Q(profile__unique_id__iexact=f"CZ-{ident_str}")
            ).first()
            
        if not target:
            messages.error(request, f"User '{user_identifier}' not found.")
        elif target.is_superuser:
            messages.error(request, "Cannot ban a superuser account.")
        else:
            target.is_active = False
            target.save()
            uid = getattr(target, 'profile', None) and target.profile.unique_id
            messages.warning(request, f"User '{target.username}' (User ID: {uid or 'None'}) has been BANNED / SUSPENDED.")
        return redirect(f"{admin_base}?tab={redirect_tab}")

    elif action_type == 'unban_user':
        user_identifier = request.POST.get('user_identifier') or request.POST.get('user_id')
        if not user_identifier:
            messages.error(request, "Please enter a username or User ID to restore.")
            return redirect(f"{admin_base}?tab={redirect_tab}")
            
        target = None
        ident_str = str(user_identifier).strip()
        if ident_str.isdigit():
            target = User.objects.filter(id=int(ident_str)).first()
        if not target:
            target = User.objects.filter(
                Q(username__iexact=ident_str) |
                Q(profile__unique_id__iexact=ident_str) |
                Q(profile__unique_id__iexact=f"CZ-{ident_str}")
            ).first()
            
        if not target:
            messages.error(request, f"User '{user_identifier}' not found.")
        else:
            target.is_active = True
            target.save()
            messages.success(request, f"User '{target.username}' has been RESTORED (Active).")
        return redirect(f"{admin_base}?tab={redirect_tab}")

    elif action_type == 'issue_emergency_pin':
        user_id = request.POST.get('user_id')
        try:
            target = User.objects.select_related('profile').get(id=user_id)
            pin = f"{secrets.randbelow(900000) + 100000}"
            target.profile.emergency_pin = pin
            target.profile.emergency_pin_expires_at = timezone.now() + timezone.timedelta(hours=2)
            target.profile.save()
            messages.success(request, f"🔑 Generated Emergency Recovery PIN for @{target.username} (User ID: {target.profile.unique_id}): {pin} (Valid for 2 hours). Share this with the user to recover their account.")
        except User.DoesNotExist:
            messages.error(request, "User not found.")
        return redirect(f"{admin_base}?tab={redirect_tab}")

    elif action_type == 'force_terminate_sessions':
        user_id = request.POST.get('user_id')
        try:
            target = User.objects.get(id=user_id)
            user_id_str = str(target.id)
            purged = 0
            for s in Session.objects.filter(expire_date__gte=timezone.now()):
                try:
                    if str(s.get_decoded().get('_auth_user_id')) == user_id_str:
                        s.delete()
                        purged += 1
                except Exception:
                    pass
            messages.success(request, f"Terminated {purged} active sessions across all devices for @{target.username}.")
        except User.DoesNotExist:
            messages.error(request, "User not found.")
        return redirect(f"{admin_base}?tab={redirect_tab}")

    elif action_type == 'delete_message':
        msg_id = request.POST.get('message_id')
        msg_type = request.POST.get('msg_type', 'channel')
        if msg_type == 'dm':
            try:
                dm = DirectMessage.objects.get(id=msg_id)
                dm.delete()
                messages.success(request, f"Direct Message #{msg_id} was PERMANENTLY DELETED.")
            except DirectMessage.DoesNotExist:
                messages.error(request, f"Direct Message #{msg_id} not found.")
        else:
            try:
                msg = Message.objects.get(id=msg_id)
                channel_name = msg.channel.name
                msg.delete()
                messages.success(request, f"Message #{msg_id} in #{channel_name} was PERMANENTLY DELETED.")
            except Message.DoesNotExist:
                messages.error(request, f"Message #{msg_id} not found.")
        return redirect(f"{admin_base}?tab={redirect_tab}")

    return redirect(f"{admin_base}?tab={redirect_tab}")
