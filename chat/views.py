from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q
import re
from .models import Community, Channel, ChannelCategory, Message, CommunityMember, ChannelReadState

@login_required
def chat_view(request, channel_slug=None):
    if channel_slug:
        active_channel = get_object_or_404(Channel, slug=channel_slug)
        community = active_channel.category.community
    else:
        community_slug = request.GET.get('c')
        if community_slug:
            community = Community.objects.filter(slug=community_slug).first()
        else:
            # Fallback to user's first community
            membership = CommunityMember.objects.filter(user=request.user).first()
            community = membership.community if membership else None
            
        if not community:
            from chat.services import ChatService
            official = Community.objects.filter(is_verified=True).first() or ChatService.get_or_create_official_community(owner=request.user)
            if official:
                return redirect(f"/community/chat/?c={official.slug}")
            return redirect('create_community')
            
        active_channel = Channel.objects.filter(category__community=community).first()

    categories = ChannelCategory.objects.filter(community=community).prefetch_related('channels')
    
    # Lazy member creation
    if request.user.is_authenticated:
        membership, _ = CommunityMember.objects.get_or_create(community=community, user=request.user)
    else:
        membership = None
        
    # UI Permissions
    is_owner = (request.user == community.owner)
    can_view_channel = is_owner or (membership and membership.has_permission('VIEW_CHANNEL'))
    can_read_history = is_owner or (membership and membership.has_permission('READ_MESSAGE_HISTORY'))
    can_send_messages = is_owner or (membership and membership.has_permission('SEND_MESSAGES'))
    can_embed_links = is_owner or (membership and membership.has_permission('EMBED_LINKS'))
    can_attach_files = is_owner or (membership and membership.has_permission('ATTACH_FILES'))
    can_manage_channels = is_owner or (membership and membership.has_permission('MANAGE_CHANNELS'))
    can_manage_messages = is_owner or (membership and membership.has_permission('MANAGE_MESSAGES'))
    can_kick_members = is_owner or (membership and membership.has_permission('KICK_MEMBERS'))
    can_ban_members = is_owner or (membership and membership.has_permission('BAN_MEMBERS'))
    can_manage_roles = is_owner or (membership and membership.has_permission('MANAGE_ROLES'))
    can_connect_voice = is_owner or (membership and membership.has_permission('CONNECT_VOICE'))
    can_speak_voice = is_owner or (membership and membership.has_permission('SPEAK'))
    
    if active_channel and can_view_channel:
        if can_read_history:
            messages = active_channel.messages.select_related('author').order_by('-created_at')[:50]
            messages = list(reversed(list(messages)))
        else:
            messages = []
            
        # Prefetch memberships to get role colors efficiently
        memberships_dict = {
            m.user_id: m for m in CommunityMember.objects.filter(
                community=community, 
                user_id__in=[msg.author_id for msg in messages] if can_read_history else []
            ).prefetch_related('roles')
        }
        for msg in messages:
            m = memberships_dict.get(msg.author_id)
            if m:
                highest_role = m.highest_role
                msg.author_color = highest_role.color if highest_role else None
            else:
                msg.author_color = None

        if messages and request.user.is_authenticated:
            try:
                ChannelReadState.objects.update_or_create(
                    user=request.user,
                    channel=active_channel,
                    defaults={'last_read_message_id': messages[-1].id}
                )
            except Exception:
                pass
    else:
        messages = []



    memberships = list(CommunityMember.objects.filter(community=community).select_related('user', 'user__profile').prefetch_related('roles').order_by('user__username'))

    # Group members by highest role
    roles = list(community.roles.exclude(name='@everyone').order_by('-position', 'id'))
    
    role_member_groups = []
    assigned_user_ids = set()
    
    for r in roles:
        group_members = [
            m for m in memberships 
            if m.highest_role and m.highest_role.id == r.id and getattr(m.user.profile, 'status_setting', 'online') != 'offline'
        ]
        if group_members:
            role_member_groups.append({
                'name': r.name.upper(),
                'color': r.color,
                'count': len(group_members),
                'members': group_members
            })
            for m in group_members:
                assigned_user_ids.add(m.user_id)
                
    # Remaining online/other members
    online_members = [
        m for m in memberships 
        if m.user_id not in assigned_user_ids and getattr(m.user.profile, 'status_setting', 'online') != 'offline'
    ]
    if online_members:
        role_member_groups.append({
            'name': 'ONLINE',
            'color': None,
            'count': len(online_members),
            'members': online_members
        })
        for m in online_members:
            assigned_user_ids.add(m.user_id)
            
    # Offline members
    offline_members = [
        m for m in memberships 
        if m.user_id not in assigned_user_ids
    ]
    if offline_members:
        role_member_groups.append({
            'name': 'OFFLINE',
            'color': None,
            'count': len(offline_members),
            'members': offline_members
        })

    user_data = []
    for m in memberships:
        highest_role = m.highest_role
        color = highest_role.color if highest_role else '#F5F5F5'
        user_data.append({'username': m.user.username, 'color': color})
        
    channel_data = []
    for cat in categories:
        for ch in cat.channels.all():
            channel_data.append({'name': ch.name, 'slug': ch.slug})
            
    community_data = {'users': user_data, 'channels': channel_data}

    context = {
        'community': community,
        'categories': categories,
        'active_channel': active_channel,
        'chat_messages': messages,
        'community_memberships': memberships,
        'role_member_groups': role_member_groups,
        'community_data': community_data,
        'can_view_channel': can_view_channel,
        'can_send_messages': can_send_messages,
        'can_embed_links': can_embed_links,
        'can_attach_files': can_attach_files,
        'can_manage_channels': can_manage_channels,
        'can_manage_messages': can_manage_messages,
        'can_kick_members': can_kick_members,
        'can_ban_members': can_ban_members,
        'can_manage_roles': can_manage_roles,
        'can_connect_voice': can_connect_voice,
        'can_speak_voice': can_speak_voice,
    }
    
    # REST API Fallback - Resolves Template Coupling Con
    from django.http import JsonResponse
    if request.headers.get('Accept') == 'application/json' or request.GET.get('format') == 'json':
        return JsonResponse({
            'community': community.name,
            'channels': community_data['channels'],
            'users': community_data['users']
        })

    return render(request, 'community/chat.html', context)

@login_required
def dm_view(request, username):
    target_user = get_object_or_404(User, username=username)
    from .models import DirectMessageSession, DirectMessage
    
    session = DirectMessageSession.objects.filter(user1=request.user, user2=target_user).first()
    if not session:
        session = DirectMessageSession.objects.filter(user1=target_user, user2=request.user).first()
        
    if not session:
        session = DirectMessageSession.objects.create(user1=request.user, user2=target_user)
        
    messages = DirectMessage.objects.filter(session=session).order_by('created_at')
    
    from django.db.models import Q
    dm_sessions = DirectMessageSession.objects.filter(Q(user1=request.user) | Q(user2=request.user)).order_by('-updated_at')
    
    return render(request, 'chat/dm.html', {
        'session': session,
        'target_user': target_user,
        'chat_messages': messages,
        'dm_sessions': dm_sessions
    })

@login_required
def add_channel(request, category_id):
    category = get_object_or_404(ChannelCategory, id=category_id)
    membership = CommunityMember.objects.filter(community=category.community, user=request.user).first()
    can_manage = request.user.is_superuser or request.user == category.community.owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_CHANNELS')))
    if not can_manage:
        return render(request, '403.html', status=403)
    
    community = category.community
    categories = ChannelCategory.objects.filter(community=community).prefetch_related('channels')
    
    from .forms import ChannelForm
    from .models import AuditLog
    if request.method == 'POST':
        form = ChannelForm(request.POST)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.category = category
            from django.utils.text import slugify
            import uuid
            channel.slug = slugify(channel.name) or str(uuid.uuid4())[:8]
            if Channel.objects.filter(slug=channel.slug).exists():
                channel.slug = f"{channel.slug}-{str(uuid.uuid4())[:4]}"
            channel.save()
            AuditLog.objects.create(community=community, user=request.user, action=f"Created #{channel.name} channel in {category.name}")
            messages.success(request, f"Channel #{channel.name} created successfully!")
            return redirect('chat_channel', channel_slug=channel.slug)
        else:
            messages.error(request, "Please fix the validation errors below.")
    else:
        form = ChannelForm()
    
    return render(request, 'chat/add_channel.html', {
        'form': form, 
        'category': category,
        'community': community,
        'categories': categories
    })

@login_required
def manage_category(request, category_id):
    category = get_object_or_404(ChannelCategory, id=category_id)
    membership = CommunityMember.objects.filter(community=category.community, user=request.user).first()
    can_manage = request.user.is_superuser or request.user == category.community.owner or (membership and (membership.has_permission('ADMINISTRATOR') or membership.has_permission('MANAGE_CHANNELS')))
    if not can_manage:
        return render(request, '403.html', status=403)
    
    community = category.community
    categories = ChannelCategory.objects.filter(community=community).prefetch_related('channels')
    
    from .forms import CategoryForm
    from .models import AuditLog
    if request.method == 'POST':
        if 'delete' in request.POST:
            cat_name = category.name
            category.delete()
            AuditLog.objects.create(community=community, user=request.user, action=f"Deleted category '{cat_name}'")
            messages.success(request, f"Category '{cat_name}' deleted.")
            return redirect('chat')
        
        # Handle delete channel
        if 'delete_channel' in request.POST:
            channel_id = request.POST.get('delete_channel')
            ch = Channel.objects.filter(id=channel_id, category=category).first()
            if ch:
                ch_name = ch.name
                ch.delete()
                AuditLog.objects.create(community=community, user=request.user, action=f"Deleted channel #{ch_name}")
                messages.success(request, f"Channel #{ch_name} deleted.")
            return redirect('manage_category', category_id=category.id)
        
        # Handle move channels
        for key, value in request.POST.items():
            if key.startswith('move_channel_') and value:
                ch_id = key.replace('move_channel_', '')
                target_cat = ChannelCategory.objects.filter(id=value, community=community).first()
                if target_cat:
                    ch = Channel.objects.filter(id=ch_id, category=category).first()
                    if ch:
                        ch.category = target_cat
                        ch.save()
                        AuditLog.objects.create(community=community, user=request.user, action=f"Moved #{ch.name} to {target_cat.name}")
        
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(community=community, user=request.user, action=f"Updated category '{category.name}'")
            messages.success(request, "Category updated.")
            return redirect('manage_category', category_id=category.id)
        else:
            messages.error(request, "Please fix the validation errors below.")
    else:
        form = CategoryForm(instance=category)
        
    return render(request, 'chat/manage_category.html', {
        'form': form, 
        'category': category,
        'community': community,
        'categories': categories
    })

@login_required
def move_channel(request, channel_id):
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    channel = get_object_or_404(Channel, id=channel_id)
    community = channel.category.community
    
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    if not (request.user == community.owner or (membership and membership.has_permission('MANAGE_CHANNELS'))):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    
    category_id = request.POST.get('category_id')
    target_category = get_object_or_404(ChannelCategory, id=category_id, community=community)
    
    channel.category = target_category
    channel.save()
    
    return JsonResponse({'status': 'ok'})

@login_required
def edit_channel(request, channel_slug):
    channel = get_object_or_404(Channel, slug=channel_slug)
    community = channel.category.community
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    
    if not (request.user == community.owner or (membership and membership.has_permission('MANAGE_CHANNELS'))):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Forbidden'}, status=403)
        return render(request, '403.html', {'message': 'You do not have permission to manage channels.'}, status=403)
        
    from .forms import ChannelForm
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        # Channel type cannot be changed once channel has been created
        post_data['channel_type'] = channel.channel_type
        if 'topic' in post_data and 'description' not in post_data:
            post_data['description'] = post_data['topic']
            
        form = ChannelForm(post_data, instance=channel)
        if form.is_valid():
            channel = form.save()
            
            # Audit log
            try:
                from .models import AuditLog
                AuditLog.objects.create(
                    community=community,
                    user=request.user,
                    action='UPDATE_CHANNEL',
                    details=f"Updated channel #{channel.name} settings"
                )
            except Exception:
                pass
            
            # Handle permissions
            permissions_json = request.POST.get('permissions_json')
            if permissions_json:
                import json
                try:
                    perms_data = json.loads(permissions_json)
                    from .models import ChannelPermission
                    submitted_role_ids = set()
                    submitted_user_ids = set()
                    
                    def map_val(v):
                        if v is True or v == 'true' or v == 1: return True
                        if v is False or v == 'false' or v == 0: return False
                        return None
                        
                    for item in perms_data:
                        role_id = item.get('role_id')
                        user_id = item.get('user_id')
                        perms = item.get('perms', {})
                        
                        if role_id:
                            submitted_role_ids.add(role_id)
                            perm_obj, _ = ChannelPermission.objects.get_or_create(channel=channel, role_id=role_id)
                        elif user_id:
                            submitted_user_ids.add(user_id)
                            perm_obj, _ = ChannelPermission.objects.get_or_create(channel=channel, user_id=user_id)
                        else:
                            continue
                            
                        perm_obj.view_channel = map_val(perms.get('view_channel'))
                        perm_obj.manage_channel = map_val(perms.get('manage_channel'))
                        perm_obj.manage_permissions = map_val(perms.get('manage_permissions'))
                        perm_obj.send_messages = map_val(perms.get('send_messages'))
                        perm_obj.send_embeds = map_val(perms.get('send_embeds'))
                        perm_obj.attach_files = map_val(perms.get('attach_files'))
                        perm_obj.connect_voice = map_val(perms.get('connect_voice'))
                        perm_obj.speak_voice = map_val(perms.get('speak_voice'))
                        perm_obj.save()

                    # Clean up member overrides that were removed
                    ChannelPermission.objects.filter(channel=channel, user__isnull=False).exclude(user_id__in=submitted_user_ids).delete()
                    # Clean up role overrides that were explicitly removed (except @everyone which always persists if needed)
                    if submitted_role_ids:
                        ChannelPermission.objects.filter(channel=channel, role__isnull=False).exclude(role_id__in=submitted_role_ids).delete()
                except Exception as e:
                    print("Error saving permissions:", e)
                    
            from django.contrib import messages
            messages.success(request, f"Channel #{channel.name} updated successfully.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
                return JsonResponse({'status': 'ok', 'slug': channel.slug, 'name': channel.name})
            return redirect('chat_channel', channel_slug=channel.slug)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': form.errors.as_json()}, status=400)
    else:
        form = ChannelForm(instance=channel)
        
    return render(request, 'chat/edit_channel.html', {
        'form': form,
        'channel': channel,
        'community': community
    })

@login_required
def delete_channel(request, channel_slug):
    if request.method == 'POST':
        channel = get_object_or_404(Channel, slug=channel_slug)
        community = channel.category.community
        membership = CommunityMember.objects.filter(community=community, user=request.user).first()
        
        if not (request.user == community.owner or (membership and membership.has_permission('MANAGE_CHANNELS'))):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Forbidden'}, status=403)
            return render(request, '403.html', {'message': 'You do not have permission to delete channels.'}, status=403)
            
        c_name = channel.name
        channel.delete()
        try:
            from .models import AuditLog
            AuditLog.objects.create(
                community=community,
                user=request.user,
                action='DELETE_CHANNEL',
                details=f"Deleted channel #{c_name}"
            )
        except Exception:
            pass
            
        from django.contrib import messages
        messages.success(request, f"Channel #{c_name} deleted successfully.")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok'})
        return redirect('chat')
    return redirect('chat')

@login_required
def get_channel_permissions(request, channel_slug):
    channel = get_object_or_404(Channel, slug=channel_slug)
    community = channel.category.community
    
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    if not (request.user == community.owner or (membership and membership.has_permission('MANAGE_CHANNELS'))):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    
    # Return all roles for this community
    roles = community.roles.all().order_by('-position')
    
    permissions_data = []
    from .models import ChannelPermission
    for role in roles:
        perm, _ = ChannelPermission.objects.get_or_create(channel=channel, role=role)
        perms_dict = {
            'view_channel': perm.view_channel,
            'manage_channel': perm.manage_channel,
            'manage_permissions': perm.manage_permissions,
            'send_messages': perm.send_messages,
            'send_embeds': perm.send_embeds,
            'attach_files': perm.attach_files,
            'connect_voice': perm.connect_voice,
            'speak_voice': perm.speak_voice,
        }
        has_overrides = any(v is not None for v in perms_dict.values())
        permissions_data.append({
            'role_id': role.id,
            'role_name': role.name,
            'color': role.color,
            'is_member': False,
            'has_overrides': has_overrides,
            'perms': perms_dict
        })
        
    # User-specific channel permission overrides
    user_perms = ChannelPermission.objects.filter(channel=channel, user__isnull=False).select_related('user', 'user__profile')
    for uperm in user_perms:
        u = uperm.user
        membership = community.members.filter(user=u).first()
        hr = membership.highest_role if membership else None
        perms_dict = {
            'view_channel': uperm.view_channel,
            'manage_channel': uperm.manage_channel,
            'manage_permissions': uperm.manage_permissions,
            'send_messages': uperm.send_messages,
            'send_embeds': uperm.send_embeds,
            'attach_files': uperm.attach_files,
            'connect_voice': uperm.connect_voice,
            'speak_voice': uperm.speak_voice,
        }
        has_overrides = any(v is not None for v in perms_dict.values())
        permissions_data.append({
            'user_id': u.id,
            'role_name': u.username,
            'avatar': u.profile.get_avatar_url(),
            'color': hr.color if hr else '#99AAB5',
            'is_member': True,
            'has_overrides': has_overrides,
            'perms': perms_dict
        })
        
    # All community roles
    all_roles_data = []
    for r in roles:
        all_roles_data.append({
            'role_id': r.id,
            'role_name': r.name,
            'color': r.color,
            'is_everyone': (r.name == '@everyone')
        })

    # Community members for override selection
    members_data = []
    for m in community.members.select_related('user', 'user__profile').prefetch_related('roles'):
        hr = m.highest_role
        members_data.append({
            'user_id': m.user.id,
            'username': m.user.username,
            'avatar': m.user.profile.get_avatar_url(),
            'color': hr.color if hr else '#99AAB5'
        })
        
    channel_data = {
        'id': channel.id,
        'slug': channel.slug,
        'name': channel.name,
        'topic': channel.description or '',
        'channel_type': channel.channel_type,
        'cooldown': channel.cooldown,
        'user_limit': channel.user_limit,
        'bitrate': channel.bitrate,
        'is_private': channel.is_private,
        'owner_username': community.owner.username if community.owner else '',
        'delete_url': f"/community/chat/channel/{channel.slug}/delete/"
    }
    return JsonResponse({
        'channel': channel_data, 
        'roles': permissions_data,
        'all_roles': all_roles_data,
        'members': members_data
    })


@login_required
def search_messages(request):
    community_slug = request.GET.get('c')
    channel_slug = request.GET.get('channel')
    query_str = request.GET.get('q', '').strip()
    from_user = request.GET.get('from', '').strip()
    mention_user = request.GET.get('mention', '').strip()
    in_channel = request.GET.get('in', '').strip()
    has_type = request.GET.get('has', '').strip().lower()
    sort_order = request.GET.get('sort', 'newest').strip().lower()

    # Extract tokens from query string if present
    from_match = re.search(r'\bfrom:([^\s]+)', query_str, re.IGNORECASE)
    if from_match:
        from_user = from_user or from_match.group(1).lstrip('@')
        query_str = re.sub(r'\bfrom:[^\s]+', '', query_str, flags=re.IGNORECASE)

    mention_match = re.search(r'\bmentions?:([^\s]+)', query_str, re.IGNORECASE)
    if mention_match:
        mention_user = mention_user or mention_match.group(1).lstrip('@')
        query_str = re.sub(r'\bmentions?:[^\s]+', '', query_str, flags=re.IGNORECASE)

    in_match = re.search(r'\bin:([^\s]+)', query_str, re.IGNORECASE)
    if in_match:
        in_channel = in_channel or in_match.group(1).lstrip('#')
        query_str = re.sub(r'\bin:[^\s]+', '', query_str, flags=re.IGNORECASE)

    has_match = re.search(r'\bhas:([^\s]+)', query_str, re.IGNORECASE)
    if has_match:
        has_type = has_type or has_match.group(1).lower()
        query_str = re.sub(r'\bhas:[^\s]+', '', query_str, flags=re.IGNORECASE)

    sort_match = re.search(r'\bsort:([^\s]+)', query_str, re.IGNORECASE)
    if sort_match:
        sort_order = sort_order or sort_match.group(1).lower()
        query_str = re.sub(r'\bsort:[^\s]+', '', query_str, flags=re.IGNORECASE)

    clean_q = query_str.strip()

    # Identify community
    community = None
    if community_slug:
        community = Community.objects.filter(slug=community_slug).first()
    elif channel_slug:
        ch = Channel.objects.filter(slug=channel_slug).first()
        if ch:
            community = ch.category.community

    if not community:
        membership = CommunityMember.objects.filter(user=request.user).first()
        community = membership.community if membership else None

    if not community:
        return JsonResponse({'results': [], 'count': 0, 'filters': {}})

    # Determine accessible channels for user
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    is_owner = (request.user == community.owner)
    
    accessible_channels = []
    user_roles = list(membership.roles.all()) if membership else []
    everyone_role = community.roles.filter(name='@everyone').first()

    for ch in Channel.objects.filter(category__community=community):
        if is_owner:
            accessible_channels.append(ch.id)
            continue
        # User override
        user_override = ch.permissions.filter(user=request.user).first()
        if user_override and user_override.view_channel is not None:
            if user_override.view_channel:
                accessible_channels.append(ch.id)
            continue
        # Role override
        role_override = ch.permissions.filter(role__in=user_roles, view_channel__isnull=False).first()
        if role_override and role_override.view_channel is not None:
            if role_override.view_channel:
                accessible_channels.append(ch.id)
            continue
        # Everyone override
        if everyone_role:
            ev_override = ch.permissions.filter(role=everyone_role, view_channel__isnull=False).first()
            if ev_override and ev_override.view_channel is not None:
                if ev_override.view_channel:
                    accessible_channels.append(ch.id)
                continue
        # Base role permission
        if not ch.is_private and (membership and membership.has_permission('VIEW_CHANNEL')):
            accessible_channels.append(ch.id)

    messages_qs = Message.objects.filter(channel_id__in=accessible_channels)

    # Filter in:channel
    if in_channel:
        messages_qs = messages_qs.filter(
            Q(channel__name__iexact=in_channel) | 
            Q(channel__slug__iexact=in_channel) |
            Q(channel__name__icontains=in_channel)
        )

    # Filter from:user
    if from_user:
        messages_qs = messages_qs.filter(author__username__icontains=from_user)

    # Filter mention:user
    if mention_user:
        target_name = request.user.username if mention_user.lower() == 'me' else mention_user
        messages_qs = messages_qs.filter(
            Q(content__icontains=f"@{target_name}") |
            Q(reply_to__author__username__iexact=target_name)
        )

    # Filter has:type
    if has_type in ['image', 'images']:
        messages_qs = messages_qs.filter(
            Q(attachment__endswith='.png') | Q(attachment__endswith='.jpg') | 
            Q(attachment__endswith='.jpeg') | Q(attachment__endswith='.gif') | 
            Q(attachment__endswith='.webp')
        )
    elif has_type in ['file', 'files']:
        messages_qs = messages_qs.filter(attachment__isnull=False).exclude(attachment='')
    elif has_type in ['link', 'links']:
        messages_qs = messages_qs.filter(
            Q(content__icontains='http://') | Q(content__icontains='https://')
        )
    elif has_type in ['embed', 'embeds']:
        messages_qs = messages_qs.filter(embed_data__isnull=False)

    # Filter query text
    if clean_q:
        messages_qs = messages_qs.filter(content__icontains=clean_q)

    # Sorting
    if sort_order == 'oldest':
        messages_qs = messages_qs.order_by('created_at')
    else:
        sort_order = 'newest'
        messages_qs = messages_qs.order_by('-created_at')

    total_count = messages_qs.count()
    results = list(messages_qs.select_related('author', 'author__profile', 'channel')[:50])

    author_ids = [m.author_id for m in results]
    memberships_dict = {
        m.user_id: m for m in CommunityMember.objects.filter(
            community=community, user_id__in=author_ids
        ).prefetch_related('roles')
    }

    serialized = []
    for msg in results:
        m = memberships_dict.get(msg.author_id)
        hr = m.highest_role if m else None
        
        att_url = None
        is_image = False
        if msg.attachment:
            try:
                att_url = msg.attachment.url
                lower_att = msg.attachment.name.lower()
                is_image = any(lower_att.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])
            except Exception:
                pass

        serialized.append({
            'id': msg.id,
            'channel_name': msg.channel.name,
            'channel_slug': msg.channel.slug,
            'author': msg.author.username,
            'author_avatar': msg.author.profile.get_avatar_url(),
            'author_color': hr.color if hr else '#F5F5F5',
            'content': msg.content,
            'created_at': msg.created_at.strftime('%b %d, %Y %I:%M %p'),
            'date_short': msg.created_at.strftime('%b %d, %I:%M %p'),
            'has_attachment': bool(msg.attachment),
            'attachment_url': att_url,
            'is_image': is_image,
            'has_embed': bool(msg.embed_data)
        })

    return JsonResponse({
        'results': serialized,
        'count': total_count,
        'filters': {
            'q': clean_q,
            'from': from_user,
            'mention': mention_user,
            'in': in_channel,
            'has': has_type,
            'sort': sort_order
        }
    })


@login_required
def get_notifications(request):
    community_slug = request.GET.get('c')
    community = None
    if community_slug:
        community = Community.objects.filter(slug=community_slug).first()
    if not community:
        membership = CommunityMember.objects.filter(user=request.user).first()
        community = membership.community if membership else None

    if not community:
        return JsonResponse({
            'mentions': [], 
            'unreads': [], 
            'unread_mention_count': 0, 
            'unread_messages_count': 0, 
            'total_badge_count': 0
        })

    read_states = {
        rs.channel_id: rs.last_read_message_id 
        for rs in ChannelReadState.objects.filter(user=request.user, channel__category__community=community)
    }

    # 1. Mentions directed at the current user
    mentions_qs = Message.objects.filter(
        channel__category__community=community
    ).filter(
        Q(content__icontains=f"@{request.user.username}") | 
        Q(content__icontains="@everyone") | 
        Q(reply_to__author=request.user)
    ).exclude(
        author=request.user
    ).select_related('author', 'author__profile', 'channel').order_by('-created_at')[:30]

    mentions_data = []
    unread_mention_count = 0
    for m in mentions_qs:
        last_read_id = read_states.get(m.channel_id, 0)
        is_unread = (m.id > last_read_id)
        if is_unread:
            unread_mention_count += 1

        mentions_data.append({
            'id': m.id,
            'channel_name': m.channel.name,
            'channel_slug': m.channel.slug,
            'author': m.author.username,
            'author_avatar': m.author.profile.get_avatar_url(),
            'content': m.content[:120],
            'created_at': m.created_at.strftime('%b %d, %I:%M %p'),
            'is_unread': is_unread
        })

    # 2. Unread messages grouped by channel
    channels = Channel.objects.filter(category__community=community, channel_type='text')
    unreads_data = []
    total_unread_messages = 0

    for ch in channels:
        last_read_id = read_states.get(ch.id, 0)
        unread_msgs = ch.messages.filter(id__gt=last_read_id).exclude(author=request.user).select_related('author', 'author__profile').order_by('-id')
        count = unread_msgs.count()
        if count > 0:
            total_unread_messages += count
            latest = unread_msgs.first()
            unreads_data.append({
                'channel_name': ch.name,
                'channel_slug': ch.slug,
                'unread_count': count,
                'latest_author': latest.author.username,
                'latest_avatar': latest.author.profile.get_avatar_url(),
                'latest_content': latest.content[:80],
                'latest_time': latest.created_at.strftime('%I:%M %p')
            })

    return JsonResponse({
        'mentions': mentions_data,
        'unreads': unreads_data,
        'unread_mention_count': unread_mention_count,
        'unread_messages_count': total_unread_messages,
        'total_badge_count': unread_mention_count + total_unread_messages
    })


@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        community_slug = request.POST.get('c')
        channel_slug = request.POST.get('channel')

        if channel_slug:
            ch = Channel.objects.filter(slug=channel_slug).first()
            if ch:
                latest = ch.messages.order_by('-id').first()
                latest_id = latest.id if latest else 0
                ChannelReadState.objects.update_or_create(
                    user=request.user,
                    channel=ch,
                    defaults={'last_read_message_id': latest_id}
                )
        elif community_slug:
            community = Community.objects.filter(slug=community_slug).first()
            if community:
                for ch in Channel.objects.filter(category__community=community):
                    latest = ch.messages.order_by('-id').first()
                    latest_id = latest.id if latest else 0
                    ChannelReadState.objects.update_or_create(
                        user=request.user,
                        channel=ch,
                        defaults={'last_read_message_id': latest_id}
                    )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=400)
