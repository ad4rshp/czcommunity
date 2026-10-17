from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from .models import DashboardConfig
from .forms import DashboardConfigForm

def home(request):
    if request.user.is_authenticated and not request.GET.get('preview'):
        if request.GET.get('open_profile'):
            c_param = f"&c={request.GET.get('c')}" if request.GET.get('c') else ""
            return redirect(f"/friends/?open_profile={request.GET.get('open_profile')}{c_param}")
        last_loc = request.COOKIES.get('cz_last_location')
        if last_loc and not last_loc.startswith('//') and (
            last_loc.startswith('/community/chat') or 
            last_loc.startswith('/friends') or 
            last_loc.startswith('/chat/dm') or 
            last_loc.startswith('/profiles/friends')
        ):
            return redirect(last_loc)
        return redirect('friends')
    from django.contrib.auth.models import User
    count = User.objects.count()
    if count >= 1000:
        users_count = f"{count:,}+"
    elif count >= 100:
        users_count = f"{count}+"
    else:
        users_count = "1,500+"
    return render(request, 'home/index.html', {'users_count': users_count})

def community_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    community_slug = request.GET.get('c')
    if community_slug:
        return redirect(f"/community/chat/?c={community_slug}")
    return redirect('chat')

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

@login_required
def community_settings(request):
    from chat.models import Community, ChannelCategory, Role, AuditLog, CommunityMember
    
    slug = request.GET.get('c')
    if slug:
        community = Community.objects.filter(slug=slug).first()
    else:
        community = Community.objects.filter(owner=request.user).first() or Community.objects.first()
        
    if not community:
        return redirect('create_community')
        
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    is_owner = (request.user == community.owner)
    has_access = is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES') or membership.has_permission('MANAGE_CHANNELS')))
    
    if not has_access:
        return render(request, 'core/community_settings.html', {
            'community': community,
            'access_denied': True,
        })
    
    config = DashboardConfig.load()
    categories = ChannelCategory.objects.filter(community=community).prefetch_related('channels') if community else []
    roles = Role.objects.filter(community=community)
    audit_logs = AuditLog.objects.filter(community=community).select_related('user')[:50]
    
    current_tab = request.GET.get('tab', 'overview')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Overview Tab
        if action == 'update_community':
            if not (is_owner or (membership and membership.has_permission('ADMINISTRATOR'))):
                messages.error(request, "You lack permission to manage server settings.")
                return redirect(f'/community/settings/?c={community.slug}&tab=overview')
            name = (request.POST.get('name') or '').strip()
            if not name:
                messages.error(request, "Server name cannot be blank.")
                return redirect(f'/community/settings/?c={community.slug}&tab=overview')
            community.name = name
            community.description = request.POST.get('description', '').strip()
            if 'icon' in request.FILES:
                icon_file = request.FILES['icon']
                if icon_file.size > 1 * 1024 * 1024:
                    messages.error(request, "Icon size must be under 1MB.")
                    return redirect(f'/community/settings/?c={community.slug}&tab=overview')
                community.icon = icon_file
            community.save()
            AuditLog.objects.create(community=community, user=request.user, action="Updated community profile")
            messages.success(request, "Server settings updated successfully!")
            return redirect(f'/community/settings/?c={community.slug}&tab=overview')

        # Dashboard Tab
        elif action == 'update_dashboard':
            if not (is_owner or (membership and membership.has_permission('ADMINISTRATOR'))):
                messages.error(request, "You lack permission to update dashboard configuration.")
                return redirect(f'/community/settings/?c={community.slug}&tab=dashboard')
            form = DashboardConfigForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                AuditLog.objects.create(community=community, user=request.user, action="Updated dashboard configuration")
                messages.success(request, "Dashboard configuration updated!")
                return redirect(f'/community/settings/?c={community.slug}&tab=dashboard')
            else:
                messages.error(request, "Please correct the form errors.")
                return redirect(f'/community/settings/?c={community.slug}&tab=dashboard')
                
        # Roles Tab
        elif action == 'create_role':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES')))):
                messages.error(request, "You lack permission to create roles.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            name = (request.POST.get('name') or '').strip()
            color = request.POST.get('color', '#99AAB5')
            if not name:
                messages.error(request, "Role name cannot be blank.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            from django.db.models import Max
            max_pos = Role.objects.filter(community=community).aggregate(Max('position'))['position__max'] or 0
            Role.objects.create(community=community, name=name, color=color, position=max_pos + 1)
            AuditLog.objects.create(community=community, user=request.user, action=f"Created role: {name}")
            messages.success(request, f"Role '{name}' created successfully!")
            return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            
        elif action == 'update_role':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES')))):
                messages.error(request, "You lack permission to update roles.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            role_id = request.POST.get('role_id')
            role = Role.objects.filter(id=role_id, community=community).first()
            if role:
                if role.name != '@everyone' and request.POST.get('name'):
                    role.name = request.POST.get('name').strip()
                if request.POST.get('color'):
                    role.color = request.POST.get('color')
                role.display_separately = request.POST.get('display_separately') == 'on'
                role.allow_mention = request.POST.get('allow_mention') == 'on'
                role.MODERATE_MEMBERS = request.POST.get('MODERATE_MEMBERS') == 'on'
                role.MANAGE_ROLES = request.POST.get('MANAGE_ROLES') == 'on'
                role.MANAGE_NICKNAMES = request.POST.get('MANAGE_NICKNAMES') == 'on'
                role.CHANGE_NICKNAME = request.POST.get('CHANGE_NICKNAME') == 'on'
                role.READ_MESSAGE_HISTORY = request.POST.get('READ_MESSAGE_HISTORY') == 'on'
                role.ATTACH_FILES = request.POST.get('ATTACH_FILES') == 'on'
                role.EMBED_LINKS = request.POST.get('EMBED_LINKS') == 'on'
                role.MANAGE_MESSAGES = request.POST.get('MANAGE_MESSAGES') == 'on'
                role.SEND_MESSAGES = request.POST.get('SEND_MESSAGES') == 'on'
                role.VIEW_CHANNEL = request.POST.get('VIEW_CHANNEL') == 'on'
                role.MANAGE_CHANNELS = request.POST.get('MANAGE_CHANNELS') == 'on'
                role.KICK_MEMBERS = request.POST.get('KICK_MEMBERS') == 'on'
                role.BAN_MEMBERS = request.POST.get('BAN_MEMBERS') == 'on'
                role.ADMINISTRATOR = request.POST.get('ADMINISTRATOR') == 'on'
                
                # Allow position updates if provided
                if request.POST.get('position'):
                    role.position = int(request.POST.get('position'))
                    
                role.save()
                AuditLog.objects.create(community=community, user=request.user, action=f"Updated permissions for role: {role.name}")
                messages.success(request, f"Permissions for role '{role.name}' saved!")
            return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            
        elif action == 'delete_role':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES')))):
                messages.error(request, "You lack permission to delete roles.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            role_id = request.POST.get('role_id')
            role = Role.objects.filter(id=role_id, community=community).first()
            if role and role.name != '@everyone':
                name = role.name
                role.delete()
                AuditLog.objects.create(community=community, user=request.user, action=f"Deleted role: {name}")
                messages.success(request, f"Role '{name}' deleted.")
            return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            
        elif action == 'create_invite':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES')))):
                messages.error(request, "You lack permission to create invite links.")
                return redirect(f'/community/settings/?c={community.slug}&tab=invites')
            
            try:
                max_uses = int(request.POST.get('max_uses', 0))
                if max_uses < 0:
                    messages.error(request, "Max uses cannot be negative.")
                    return redirect(f'/community/settings/?c={community.slug}&tab=invites')
                if max_uses > 10000:
                    messages.error(request, "Max uses cannot exceed 10,000.")
                    return redirect(f'/community/settings/?c={community.slug}&tab=invites')
            except (ValueError, TypeError):
                messages.error(request, "Invalid number for max uses.")
                return redirect(f'/community/settings/?c={community.slug}&tab=invites')

            try:
                expires_in_days = int(request.POST.get('expires_in', 0))
                if expires_in_days < 0:
                    expires_in_days = 0
            except (ValueError, TypeError):
                expires_in_days = 0

            from chat.models import CommunityInvite
            import uuid
            from django.utils import timezone
            import datetime

            expires_at = None
            if expires_in_days > 0:
                expires_at = timezone.now() + datetime.timedelta(days=expires_in_days)
                
            code = str(uuid.uuid4())[:8].lower()
            CommunityInvite.objects.create(
                community=community,
                code=code,
                created_by=request.user,
                max_uses=max_uses,
                expires_at=expires_at
            )
            AuditLog.objects.create(community=community, user=request.user, action=f"Created invite code: {code}")
            messages.success(request, f"Generated new invite code: {code}")
            return redirect(f'/community/settings/?c={community.slug}&tab=invites')
            
        elif action == 'delete_invite':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES')))):
                messages.error(request, "You lack permission to revoke invites.")
                return redirect(f'/community/settings/?c={community.slug}&tab=invites')
            from chat.models import CommunityInvite
            invite_id = request.POST.get('invite_id')
            invite = CommunityInvite.objects.filter(id=invite_id, community=community).first()
            if invite:
                code = invite.code
                invite.delete()
                AuditLog.objects.create(community=community, user=request.user, action=f"Deleted invite code: {code}")
                messages.success(request, f"Revoked invite code: {code}")
            return redirect(f'/community/settings/?c={community.slug}&tab=invites')

    else:
        form = DashboardConfigForm(instance=config)
        
    from chat.models import CommunityInvite
    invites = CommunityInvite.objects.filter(community=community).order_by('-created_at')
    
    # Mark expired invites
    from django.utils import timezone
    now = timezone.now()
    for inv in invites:
        inv.is_expired = False
        if inv.expires_at and inv.expires_at < now:
            inv.is_expired = True
        if inv.max_uses > 0 and inv.uses >= inv.max_uses:
            inv.is_expired = True
        
    return render(request, 'core/community_settings.html', {
        'form': form,
        'community': community,
        'categories': categories,
        'roles': roles,
        'audit_logs': audit_logs,
        'invites': invites,
        'current_tab': current_tab,
    })

@login_required
def create_community(request):
    from chat.models import Community, CommunityMember, Role, Channel, ChannelCategory, AuditLog
    from django.contrib import messages
    
    official = Community.objects.filter(is_verified=True).first()
    is_official_member = CommunityMember.objects.filter(community=official, user=request.user).exists() if official else False

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = (request.POST.get('name') or '').strip()
            if not name:
                return render(request, 'core/create_community.html', {
                    'error': 'Server name cannot be blank. Please enter a valid name.',
                    'official_community': official,
                    'is_official_member': is_official_member
                })
            if len(name) < 2:
                return render(request, 'core/create_community.html', {
                    'error': 'Server name must be at least 2 characters long.',
                    'official_community': official,
                    'is_official_member': is_official_member
                })
            if len(name) > 100:
                return render(request, 'core/create_community.html', {
                    'error': 'Server name cannot exceed 100 characters.',
                    'official_community': official,
                    'is_official_member': is_official_member
                })
                
            import uuid
            slug = name.lower().replace(' ', '-') + '-' + str(uuid.uuid4())[:8]
            community = Community.objects.create(name=name, slug=slug, owner=request.user)
            cat = ChannelCategory.objects.create(community=community, name="General", slug=f"general-{str(uuid.uuid4())[:8]}")
            Channel.objects.create(category=cat, name="general", slug=f"general-{str(uuid.uuid4())[:8]}")
            
            Role.objects.create(community=community, name="@everyone", color="#99AAB5")
            CommunityMember.objects.create(community=community, user=request.user)
            AuditLog.objects.create(community=community, user=request.user, action="Created community server")
            messages.success(request, f"Server '{community.name}' created successfully!")
            return redirect(f"/community/chat/?c={community.slug}")
                
        elif action == 'join':
            invite_code = (request.POST.get('invite_code') or '').strip()
            if invite_code:
                from chat.models import CommunityInvite
                from django.utils import timezone
                
                invite = CommunityInvite.objects.filter(code=invite_code).first()
                if invite:
                    now = timezone.now()
                    is_expired = False
                    if invite.expires_at and invite.expires_at < now:
                        is_expired = True
                    if invite.max_uses > 0 and invite.uses >= invite.max_uses:
                        is_expired = True
                        
                    if is_expired:
                        return render(request, 'core/create_community.html', {
                            'error': 'This invite code has expired or reached its maximum uses.',
                            'official_community': official,
                            'is_official_member': is_official_member
                        })
                        
                    community = invite.community
                    member, created = CommunityMember.objects.get_or_create(community=community, user=request.user)
                    if created:
                        everyone_role = Role.objects.filter(community=community, name="@everyone").first()
                        if everyone_role:
                            member.roles.add(everyone_role)
                        invite.uses += 1
                        invite.save()
                        AuditLog.objects.create(community=community, user=request.user, action=f"{request.user.username} joined via invite code '{invite_code}'")
                    messages.success(request, f"Joined {community.name}!")
                    return redirect(f"/community/chat/?c={community.slug}")
                else:
                    return render(request, 'core/create_community.html', {
                        'error': 'Invalid invite code. Please check and try again.',
                        'official_community': official,
                        'is_official_member': is_official_member
                    })

        elif action == 'join_official':
            from chat.services import ChatService
            official_comm = ChatService.get_or_create_official_community(owner=request.user)
            if official_comm:
                member, created = CommunityMember.objects.get_or_create(community=official_comm, user=request.user)
                everyone_role = Role.objects.filter(community=official_comm, name="@everyone").first()
                if everyone_role:
                    member.roles.add(everyone_role)
                messages.success(request, "Welcome to Chillzone Official!")
                return redirect(f"/community/chat/?c={official_comm.slug}")

    return render(request, 'core/create_community.html', {
        'official_community': official,
        'is_official_member': is_official_member
    })

def tos(request):
    return render(request, 'core/tos.html')

def privacy(request):
    return render(request, 'core/privacy.html')

@login_required
def delete_community_view(request):
    from chat.models import Community
    from django.contrib import messages
    slug = request.GET.get('c') or request.POST.get('community_slug')
    if slug:
        community = Community.objects.filter(slug=slug).first()
    else:
        community = Community.objects.filter(owner=request.user).first() or Community.objects.first()
    
    if not community:
        return redirect('community')

    if not request.user.is_superuser and (community.owner != request.user):
        return render(request, '403.html', status=403)
        
    if request.method == 'POST':
        if request.POST.get('action') == 'delete_community_confirm':
            name = community.name
            community.delete()
            messages.success(request, f"Server '{name}' was permanently deleted.")
            return redirect('create_community')
            
    return render(request, 'core/delete_community.html', {'community': community})

@login_required
def leave_community(request, community_id):
    from chat.models import Community, CommunityMember
    
    if request.method == 'POST':
        community = Community.objects.filter(id=community_id).first()
        if community and community.owner != request.user:
            # Delete membership
            CommunityMember.objects.filter(community=community, user=request.user).delete()
            
            # Find another community to redirect to
            next_membership = CommunityMember.objects.filter(user=request.user).first()
            if next_membership:
                return redirect(f"/community/chat/?c={next_membership.community.slug}")
            return redirect('home')
            
@login_required
def community_notification_settings(request, community_slug):
    from chat.models import Community, CommunityMember
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    
    community = get_object_or_404(Community, slug=community_slug)
    member, _ = CommunityMember.objects.get_or_create(community=community, user=request.user)
    
    if request.method == 'POST':
        level = request.POST.get('notification_level', 'all')
        if level in ['all', 'mentions', 'nothing']:
            member.notification_level = level
        member.suppress_everyone = request.POST.get('suppress_everyone') in ['true', '1', True, 'on']
        member.suppress_roles = request.POST.get('suppress_roles') in ['true', '1', True, 'on']
        member.save()
        return JsonResponse({
            'status': 'success',
            'notification_level': member.notification_level,
            'suppress_everyone': member.suppress_everyone,
            'suppress_roles': member.suppress_roles
        })
        
    return JsonResponse({
        'status': 'success',
        'community_name': community.name,
        'community_slug': community.slug,
        'notification_level': member.notification_level,
        'suppress_everyone': member.suppress_everyone,
        'suppress_roles': member.suppress_roles,
        'is_owner': (community.owner == request.user),
        'community_id': community.id
    })

def custom_404(request, exception=None):
    return render(request, '404.html', status=404)

def custom_500(request):
    return render(request, '500.html', status=500)

def custom_403(request, exception=None):
    return render(request, '403.html', status=403)
