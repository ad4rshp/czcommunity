from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from .models import DashboardConfig
from .forms import DashboardConfigForm

def home(request):
    if request.user.is_authenticated:
        return redirect('friends')
    from django.contrib.auth.models import User
    users_count = User.objects.count()
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
            name = request.POST.get('name')
            description = request.POST.get('description')
            if name:
                community.name = name
            community.description = description
            if 'icon' in request.FILES:
                icon_file = request.FILES['icon']
                # Limit server icon size to 1MB (1 * 1024 * 1024 bytes)
                if icon_file.size > 1 * 1024 * 1024:
                    return redirect('/community/settings/?tab=overview&error=Icon+size+must+be+under+1MB')
                community.icon = icon_file
            community.save()
            AuditLog.objects.create(community=community, user=request.user, action="Updated community profile")
            return redirect('/community/settings/?tab=overview')
        # Dashboard Tab
        elif action == 'update_dashboard':
            form = DashboardConfigForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                AuditLog.objects.create(community=community, user=request.user, action="Updated dashboard configuration")
                return redirect('/community/settings/?tab=dashboard')
                
        # Roles Tab
        elif action == 'create_role':
            name = request.POST.get('name')
            color = request.POST.get('color', '#99AAB5')
            if name:
                from django.db.models import Max
                max_pos = Role.objects.filter(community=community).aggregate(Max('position'))['position__max'] or 0
                Role.objects.create(community=community, name=name, color=color, position=max_pos + 1)
                AuditLog.objects.create(community=community, user=request.user, action=f"Created role: {name}")
            return redirect('/community/settings/?tab=roles')
            
        elif action == 'update_role':
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
            return redirect('/community/settings/?tab=roles')
            
        elif action == 'delete_role':
            role_id = request.POST.get('role_id')
            role = Role.objects.filter(id=role_id, community=community).first()
            if role:
                name = role.name
                role.delete()
                AuditLog.objects.create(community=community, user=request.user, action=f"Deleted role: {name}")
            return redirect('/community/settings/?tab=roles')
            
        elif action == 'create_invite':
            from chat.models import CommunityInvite
            import uuid
            from django.utils import timezone
            import datetime
            
            max_uses = int(request.POST.get('max_uses', 0))
            expires_in_days = int(request.POST.get('expires_in', 0))
            
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
            return redirect('/community/settings/?tab=invites')
            
        elif action == 'delete_invite':
            from chat.models import CommunityInvite
            invite_id = request.POST.get('invite_id')
            invite = CommunityInvite.objects.filter(id=invite_id, community=community).first()
            if invite:
                code = invite.code
                invite.delete()
                AuditLog.objects.create(community=community, user=request.user, action=f"Deleted invite code: {code}")
            return redirect('/community/settings/?tab=invites')

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
    from chat.models import Community, CommunityMember, Role, Channel, ChannelCategory
    
    # We no longer restrict creating multiple communities
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = request.POST.get('name')
            if name:
                import uuid
                slug = name.lower().replace(' ', '-') + '-' + str(uuid.uuid4())[:8]
                community = Community.objects.create(name=name, slug=slug, owner=request.user)
                cat = ChannelCategory.objects.create(community=community, name="General", slug=f"general-{str(uuid.uuid4())[:8]}")
                Channel.objects.create(category=cat, name="general", slug=f"general-{str(uuid.uuid4())[:8]}")
                
                Role.objects.create(community=community, name="@everyone", color="#99AAB5")
                CommunityMember.objects.create(community=community, user=request.user)
                
                return redirect(f"/community/chat/?c={community.slug}")
                
        elif action == 'join':
            invite_code = request.POST.get('invite_code')
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
                        return render(request, 'core/create_community.html', {'error': 'This invite code has expired or reached its maximum uses.'})
                        
                    community = invite.community
                    member, created = CommunityMember.objects.get_or_create(community=community, user=request.user)
                    if created:
                        everyone_role = Role.objects.filter(community=community, name="@everyone").first()
                        if everyone_role:
                            member.roles.add(everyone_role)
                        
                        # Increment uses
                        invite.uses += 1
                        invite.save()
                        
                    return redirect(f"/community/chat/?c={community.slug}")
                else:
                    return render(request, 'core/create_community.html', {'error': 'Invalid invite code.'})

        elif action == 'join_official':
            from chat.services import ChatService
            official = ChatService.get_or_create_official_community(owner=request.user)
            if official:
                member, created = CommunityMember.objects.get_or_create(community=official, user=request.user)
                everyone_role = Role.objects.filter(community=official, name="@everyone").first()
                if everyone_role:
                    member.roles.add(everyone_role)
                return redirect(f"/community/chat/?c={official.slug}")

    # Check official server membership status for the template
    from chat.models import Community, CommunityMember
    official = Community.objects.filter(is_verified=True).first()
    is_official_member = False
    if official and request.user.is_authenticated:
        is_official_member = CommunityMember.objects.filter(community=official, user=request.user).exists()

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
    community = Community.objects.first()
    
    if not request.user.is_superuser and (community and community.owner != request.user):
        return HttpResponseForbidden("You don't have permission to delete this community.")
        
    if request.method == 'POST':
        if request.POST.get('action') == 'delete_community_confirm':
            if community:
                community.delete()
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
            
    return redirect('home')
