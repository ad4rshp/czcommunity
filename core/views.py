import re

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
    users_count = f"{count:,}"
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
    from chat.models import Community, ChannelCategory, Role, AuditLog, CommunityMember, CommunityBan
    from chat.roles import (
        can_manage_role,
        ensure_everyone_role,
        is_role_administrator,
        manageable_roles,
        next_role_position,
        role_management_limit,
    )
    
    slug = request.GET.get('c')
    if slug:
        community = Community.objects.filter(slug=slug).first()
    else:
        community = Community.objects.filter(owner=request.user).first() or Community.objects.first()
        
    if not community:
        return redirect('create_community')

    everyone_role = ensure_everyone_role(community)
        
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    is_owner = (request.user == community.owner)
    has_access = is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES') or membership.has_permission('MANAGE_CHANNELS') or membership.has_permission('BAN_MEMBERS')))
    
    if not has_access:
        return render(request, 'core/community_settings.html', {
            'community': community,
            'access_denied': True,
        })
    
    config = DashboardConfig.load()
    categories = ChannelCategory.objects.filter(community=community).prefetch_related('channels') if community else []
    role_admin = is_role_administrator(request.user, community, membership)
    roles = list(manageable_roles(request.user, community, membership))
    roles.sort(key=lambda role: (role.name.casefold() != '@everyone', -role.position, role.name.casefold()))
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
            if len(name) > 100:
                messages.error(request, "Server names must be 100 characters or fewer.")
                return redirect(f'/community/settings/?c={community.slug}&tab=overview')
            description = (request.POST.get('description') or '').strip()
            if len(description) > 500:
                messages.error(request, "Server descriptions must be 500 characters or fewer.")
                return redirect(f'/community/settings/?c={community.slug}&tab=overview')
            community.name = name
            community.description = description
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
            if len(name) > 50:
                messages.error(request, "Role names must be 50 characters or fewer.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            if name.casefold() == '@everyone' or Role.objects.filter(
                community=community, name__iexact=name
            ).exists():
                messages.error(request, "That role name is reserved or already in use.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                color = '#99AAB5'
            position = next_role_position(community, request.user, membership)
            Role.objects.create(community=community, name=name, color=color, position=position)
            AuditLog.objects.create(community=community, user=request.user, action=f"Created role: {name}")
            messages.success(request, f"Role '{name}' created successfully!")
            return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            
        elif action == 'update_role':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_ROLES')))):
                messages.error(request, "You lack permission to update roles.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            role_id = request.POST.get('role_id')
            role = Role.objects.filter(id=role_id, community=community).first()
            if not role or not can_manage_role(request.user, community, membership, role):
                messages.error(request, "You cannot edit that role at your current role level.")
                return redirect(f'/community/settings/?c={community.slug}&tab=roles')
            if role:
                if role.name.casefold() != '@everyone' and request.POST.get('name'):
                    new_name = request.POST.get('name').strip()
                    if not new_name or new_name.casefold() == '@everyone' or Role.objects.filter(
                        community=community, name__iexact=new_name
                    ).exclude(id=role.id).exists():
                        messages.error(request, "That role name is reserved or already in use.")
                        return redirect(f'/community/settings/?c={community.slug}&tab=roles')
                    role.name = new_name[:50]
                if request.POST.get('color'):
                    requested_color = request.POST.get('color')
                    if re.fullmatch(r'#[0-9a-fA-F]{6}', requested_color):
                        role.color = requested_color
                is_everyone_role = role.name.casefold() == '@everyone'
                role.display_separately = not is_everyone_role and request.POST.get('display_separately') == 'on'
                role.allow_mention = not is_everyone_role and request.POST.get('allow_mention') == 'on'
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
                if is_everyone_role:
                    role.ADMINISTRATOR = False
                elif role_admin:
                    role.ADMINISTRATOR = request.POST.get('ADMINISTRATOR') == 'on'
                elif request.POST.get('ADMINISTRATOR') == 'on':
                    messages.error(request, "Only an owner or administrator can grant Administrator.")
                    return redirect(f'/community/settings/?c={community.slug}&tab=roles')
                
                # Allow position updates if provided
                if request.POST.get('position'):
                    try:
                        position = int(request.POST.get('position'))
                    except (TypeError, ValueError):
                        messages.error(request, "Invalid role position.")
                        return redirect(f'/community/settings/?c={community.slug}&tab=roles')
                    if not role_admin and position >= role_management_limit(membership):
                        messages.error(request, "You can only place roles below your highest role.")
                        return redirect(f'/community/settings/?c={community.slug}&tab=roles')
                    role.position = position
                    
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
            if role and role.name.casefold() != '@everyone' and can_manage_role(request.user, community, membership, role):
                name = role.name
                role.delete()
                AuditLog.objects.create(community=community, user=request.user, action=f"Deleted role: {name}")
                messages.success(request, f"Role '{name}' deleted.")
            elif role:
                messages.error(request, "You cannot delete that role at your current role level.")
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

        elif action == 'ban_member':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('BAN_MEMBERS')))):
                messages.error(request, "You lack permission to ban members.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')

            identifier = (request.POST.get('identifier') or request.POST.get('username') or '').strip()
            reason = (request.POST.get('reason') or '').strip()
            if not identifier:
                messages.error(request, "Please enter a User ID or username to ban.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')

            from chat.views import resolve_user_by_identifier
            target = resolve_user_by_identifier(identifier)
            if not target:
                messages.error(request, f"No user found matching '{identifier}'.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')

            if target == request.user:
                messages.error(request, "You cannot ban yourself.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')
            if target == community.owner:
                messages.error(request, "Cannot ban the server owner.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')
            if target.is_superuser and not request.user.is_superuser:
                messages.error(request, "Cannot ban a superuser account.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')

            # Delete membership if in server (works even if user already left server)
            CommunityMember.objects.filter(community=community, user=target).delete()

            CommunityBan.objects.update_or_create(
                community=community,
                user=target,
                defaults={'banned_by': request.user, 'reason': reason}
            )

            uid = getattr(target.profile, 'unique_id', target.id)
            AuditLog.objects.create(
                community=community,
                user=request.user,
                action=f"Banned user '{target.username}' (User ID: {uid})",
                details=f"Reason: {reason or 'No reason provided'}"
            )
            messages.success(request, f"User '{target.username}' ({uid}) has been banned from {community.name}.")
            return redirect(f'/community/settings/?c={community.slug}&tab=bans')

        elif action == 'unban_member':
            if not (is_owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('BAN_MEMBERS')))):
                messages.error(request, "You lack permission to unban members.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')

            identifier = (request.POST.get('identifier') or request.POST.get('user_id') or request.POST.get('username') or '').strip()
            from chat.views import resolve_user_by_identifier
            target = resolve_user_by_identifier(identifier)
            if not target:
                messages.error(request, f"No user found matching '{identifier}'.")
                return redirect(f'/community/settings/?c={community.slug}&tab=bans')

            deleted_count, _ = CommunityBan.objects.filter(community=community, user=target).delete()
            uid = getattr(target.profile, 'unique_id', target.id)
            if deleted_count > 0:
                AuditLog.objects.create(community=community, user=request.user, action=f"Unbanned user '{target.username}' (User ID: {uid})")
                messages.success(request, f"User '{target.username}' ({uid}) has been unbanned from {community.name}.")
            else:
                messages.info(request, f"User '{target.username}' was not banned.")
            return redirect(f'/community/settings/?c={community.slug}&tab=bans')

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
        
    bans = CommunityBan.objects.filter(community=community).select_related('user', 'user__profile', 'banned_by').order_by('-created_at')

    return render(request, 'core/community_settings.html', {
        'form': form,
        'community': community,
        'categories': categories,
        'roles': roles,
        'everyone_role': everyone_role,
        'can_grant_administrator': role_admin,
        'audit_logs': audit_logs,
        'invites': invites,
        'bans': bans,
        'current_tab': current_tab,
    })

@login_required
def create_community(request):
    from chat.models import Community, CommunityMember, Channel, ChannelCategory, AuditLog
    from chat.roles import ensure_member_default_role
    from django.contrib import messages
    from .models import DashboardConfig
    
    config = DashboardConfig.load()
    official = config.official_community or Community.objects.filter(is_verified=True).first()
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
            
            owner_member = CommunityMember.objects.create(community=community, user=request.user)
            ensure_member_default_role(owner_member)
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
                    from chat.models import CommunityBan
                    if CommunityBan.objects.filter(community=community, user=request.user).exists():
                        return render(request, 'core/create_community.html', {
                            'error': f'You are banned from "{community.name}" and cannot rejoin.',
                            'official_community': official,
                            'is_official_member': is_official_member
                        })

                    from chat.roles import ensure_member_default_role
                    member, created = CommunityMember.objects.get_or_create(community=community, user=request.user)
                    ensure_member_default_role(member)
                    if created:
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
            official_comm = config.official_community or Community.objects.filter(is_verified=True).first()
            if official_comm:
                from chat.models import CommunityBan
                if CommunityBan.objects.filter(community=official_comm, user=request.user).exists():
                    messages.error(request, f"You are banned from {official_comm.name}.")
                    return redirect('home')

                from chat.roles import ensure_member_default_role
                member, created = CommunityMember.objects.get_or_create(community=official_comm, user=request.user)
                ensure_member_default_role(member)
                messages.success(request, f"Welcome to {official_comm.name}!")
                return redirect(f"/community/chat/?c={official_comm.slug}")
            elif config.official_invite_link:
                return redirect(config.official_invite_link.strip())
            else:
                messages.info(request, "Official server is not currently set.")
                return redirect('community')

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
    from chat.roles import ensure_member_default_role
    ensure_member_default_role(member)
    
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
