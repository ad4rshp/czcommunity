from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Profile

@login_required
def member_directory(request):
    return redirect('friends')

@login_required
def profile_detail(request, username):
    user_obj = get_object_or_404(User.objects.select_related('profile'), username=username)
    from .models import Friendship, FriendRequest
    friendship = None
    friend_request = None
    if request.user != user_obj:
        friendship = Friendship.objects.filter(user1=request.user, user2=user_obj).first() or \
                     Friendship.objects.filter(user1=user_obj, user2=request.user).first()
        if not friendship:
            friend_request = FriendRequest.objects.filter(sender=request.user, receiver=user_obj).first() or \
                             FriendRequest.objects.filter(sender=user_obj, receiver=request.user).first()

    from chat.models import Community, Role, CommunityMember, AuditLog
    community_slug = request.GET.get('c') or request.POST.get('community_slug')
    community = None
    if community_slug:
        community = Community.objects.filter(slug=community_slug).first()
    elif request.method == 'POST' and request.POST.get('community_id'):
        community = Community.objects.filter(id=request.POST.get('community_id')).first()

    membership = None
    all_roles = None
    available_roles = []
    
    if community:
        membership = CommunityMember.objects.filter(community=community, user=user_obj).first()
        request_member = CommunityMember.objects.filter(community=community, user=request.user).first()
        can_manage_roles = False
        max_position = -1
        
        if request.user.is_superuser or request.user == community.owner:
            can_manage_roles = True
            max_position = 999999
        elif request_member and (request_member.has_permission('ADMINISTRATOR') or request_member.has_permission('MANAGE_ROLES')):
            can_manage_roles = True
            if request_member.has_permission('ADMINISTRATOR'):
                max_position = 999999
            else:
                highest_role = request_member.roles.exclude(name='@everyone').order_by('-position', '-id').first()
                max_position = highest_role.position if highest_role else 0
                
        if can_manage_roles:
            all_roles = Role.objects.filter(community=community).exclude(name='@everyone')
            if not (request.user.is_superuser or request.user == community.owner or (request_member and request_member.has_permission('ADMINISTRATOR'))):
                all_roles = all_roles.filter(position__lt=max_position)
                
            # Handle role assignment POST actions here to keep it on the profile page
            if request.method == 'POST':
                action = request.POST.get('role_action') or request.POST.get('action')
                if membership:
                    if action == 'assign_role':
                        role_id = request.POST.get('role_id')
                        role = all_roles.filter(id=role_id).first()
                        if role:
                            membership.roles.add(role)
                            AuditLog.objects.create(community=community, user=request.user, action=f"Assigned role {role.name} to {user_obj.username}")
                    elif action == 'remove_role':
                        role_id = request.POST.get('role_id')
                        role = Role.objects.filter(community=community, id=role_id).first()
                        if role:
                            membership.roles.remove(role)
                            AuditLog.objects.create(community=community, user=request.user, action=f"Removed role {role.name} from {user_obj.username}")
                    membership.refresh_from_db()
                return redirect(request.META.get('HTTP_REFERER', f"/profiles/{username}/?c={community.slug}"))

        if all_roles and membership:
            member_role_ids = set(membership.roles.values_list('id', flat=True))
            available_roles = [r for r in all_roles if r.id not in member_role_ids]

    if not request.headers.get('HX-Request') and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Direct URL access: redirect to SPA with query param
        c_param = f"&c={community.slug}" if community else ""
        return redirect(f"/?open_profile={username}{c_param}")

    base_template = 'base_empty.html'
    return render(request, 'profiles/detail.html', {
        'profile_user': user_obj,
        'friendship': friendship,
        'friend_request': friend_request,
        'membership': membership,
        'all_roles': all_roles,
        'available_roles': available_roles,
        'community': community,
        'base_template': base_template
    })

@login_required
def profile_card_fragment(request, username):
    user_obj = get_object_or_404(User.objects.select_related('profile'), username=username)
    
    from chat.models import Community, CommunityMember, Role, AuditLog
    from .models import Friendship, FriendRequest
    
    community_slug = request.GET.get('c') or request.POST.get('community_slug')
    membership = None
    all_roles = None
    available_roles = []
    community = None
    friendship = None
    friend_request = None
    
    if request.user != user_obj:
        friendship = Friendship.objects.filter(user1=request.user, user2=user_obj).first() or \
                     Friendship.objects.filter(user1=user_obj, user2=request.user).first()
        if not friendship:
            friend_request = FriendRequest.objects.filter(sender=request.user, receiver=user_obj).first() or \
                             FriendRequest.objects.filter(sender=user_obj, receiver=request.user).first()
                             
    if community_slug:
        community = Community.objects.filter(slug=community_slug).first()
    elif request.method == 'POST' and request.POST.get('community_id'):
        community = Community.objects.filter(id=request.POST.get('community_id')).first()
    
    if community:
        membership = CommunityMember.objects.filter(community=community, user=user_obj).first()
        request_member = CommunityMember.objects.filter(community=community, user=request.user).first()
        
        can_manage_roles = False
        max_position = -1
        
        if request.user.is_superuser or request.user == community.owner:
            can_manage_roles = True
            max_position = 999999
        elif request_member and (request_member.has_permission('ADMINISTRATOR') or request_member.has_permission('MANAGE_ROLES')):
            can_manage_roles = True
            if request_member.has_permission('ADMINISTRATOR'):
                max_position = 999999
            else:
                highest_role = request_member.roles.exclude(name='@everyone').order_by('-position', '-id').first()
                max_position = highest_role.position if highest_role else 0
                
        if can_manage_roles:
            all_roles = Role.objects.filter(community=community).exclude(name='@everyone')
            if not (request.user.is_superuser or request.user == community.owner or (request_member and request_member.has_permission('ADMINISTRATOR'))):
                all_roles = all_roles.filter(position__lt=max_position)
                
            if request.method == 'POST':
                action = request.POST.get('role_action') or request.POST.get('action')
                if membership:
                    if action == 'assign_role':
                        role_id = request.POST.get('role_id')
                        role = all_roles.filter(id=role_id).first()
                        if role:
                            membership.roles.add(role)
                            AuditLog.objects.create(community=community, user=request.user, action=f"Assigned role {role.name} to {user_obj.username}")
                    elif action == 'remove_role':
                        role_id = request.POST.get('role_id')
                        role = Role.objects.filter(community=community, id=role_id).first()
                        if role:
                            membership.roles.remove(role)
                            AuditLog.objects.create(community=community, user=request.user, action=f"Removed role {role.name} from {user_obj.username}")
                    membership.refresh_from_db()
                    
        if all_roles and membership:
            member_role_ids = set(membership.roles.values_list('id', flat=True))
            available_roles = [r for r in all_roles if r.id not in member_role_ids]
            
    return render(request, 'profiles/_card.html', {
        'profile_user': user_obj,
        'membership': membership,
        'community': community,
        'all_roles': all_roles,
        'available_roles': available_roles,
        'friendship': friendship,
        'friend_request': friend_request
    })

@login_required
def handle_friend_action(request, username):
    if request.method == 'POST':
        action = request.POST.get('action')
        target_user = get_object_or_404(User, username=username)
        from .models import Friendship, FriendRequest
        
        if action == 'add':
            if not Friendship.objects.filter(user1=request.user, user2=target_user).exists() and not Friendship.objects.filter(user1=target_user, user2=request.user).exists():
                FriendRequest.objects.get_or_create(sender=request.user, receiver=target_user)
        elif action == 'accept':
            req = FriendRequest.objects.filter(sender=target_user, receiver=request.user).first()
            if req:
                req.delete()
                Friendship.objects.get_or_create(user1=target_user, user2=request.user)
        elif action == 'reject':
            req = FriendRequest.objects.filter(sender=target_user, receiver=request.user).first()
            if req:
                req.delete()
        elif action == 'cancel':
            req = FriendRequest.objects.filter(sender=request.user, receiver=target_user).first()
            if req:
                req.delete()
        elif action == 'unfriend':
            Friendship.objects.filter(user1=request.user, user2=target_user).delete()
            Friendship.objects.filter(user1=target_user, user2=request.user).delete()
            
    return redirect('profile', username=username)

@login_required
def profile_edit(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        is_ajax = request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('ajax') == '1'
        tab = request.POST.get('current_tab', 'profile')
        
        # Account Update (Email / Account Details)
        if request.POST.get('account_update') == '1':
            email = request.POST.get('email', '').strip()
            if not email or '@' not in email or '.' not in email:
                error_msg = 'Please enter a valid email address.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
                return render(request, 'profiles/edit.html', {
                    'profile': profile,
                    'error': error_msg,
                    'base_template': 'base_empty.html' if (request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest') else 'authenticated_base.html'
                })
            request.user.email = email
            request.user.save()
            messages.success(request, 'Account email updated successfully!')
            return redirect(f"{reverse('profile_edit')}?tab=account")

        # Rotate Personal Security Recovery Key
        if request.POST.get('rotate_recovery_key') == '1':
            import secrets, string
            chars = string.ascii_uppercase + string.digits
            c1 = ''.join(secrets.choice(chars) for _ in range(4))
            c2 = ''.join(secrets.choice(chars) for _ in range(4))
            c3 = ''.join(secrets.choice(chars) for _ in range(4))
            profile.recovery_key = f"CZ-REC-{c1}-{c2}-{c3}"
            profile.save()
            messages.success(request, 'Your Security Recovery Key has been regenerated! Save your new key securely.')
            return redirect(f"{reverse('profile_edit')}?tab=account")

        # Profile Update (Display Name, Bio, Favorite Game, Status, DM Setting)
        display_name = request.POST.get('display_name', None)
        if display_name is not None:
            display_name = display_name.strip()
            if not display_name:
                error_msg = 'Display name cannot be empty.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
                return render(request, 'profiles/edit.html', {
                    'profile': profile,
                    'error': error_msg,
                    'base_template': 'base_empty.html' if (request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest') else 'authenticated_base.html'
                })
            request.user.first_name = display_name
            request.user.save()

        profile.bio = request.POST.get('bio', '')
        profile.favorite_game = request.POST.get('favorite_game', '')
        status_setting = request.POST.get('status_setting')
        if status_setting in ['online', 'idle', 'dnd', 'offline']:
            profile.status_setting = status_setting
            profile.manual_status = status_setting
        profile.dm_setting = request.POST.get('dm_setting', 'everyone')
        
        if 'avatar' in request.FILES:
            avatar_file = request.FILES['avatar']
            # Limit maximum size to 1MB (1 * 1024 * 1024 bytes)
            if avatar_file.size > 1 * 1024 * 1024:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Avatar file size must be less than 1MB.'}, status=400)
                return render(request, 'profiles/edit.html', {
                    'profile': profile,
                    'error': 'Avatar file size must be less than 1MB.',
                    'base_template': 'base_empty.html' if (request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest') else 'authenticated_base.html'
                })
            profile.avatar = avatar_file
            
        profile.save()
        
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': 'Profile settings have been updated successfully!',
                'status_setting': profile.status_setting,
                'status_display': profile.get_status_setting_display(),
                'avatar_url': profile.get_avatar_url(),
            })
            
        messages.success(request, 'Your profile settings have been updated successfully!')
        return redirect(f"{reverse('profile_edit')}?tab={tab}")
        
    base_template = 'base_empty.html' if (request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest') else 'authenticated_base.html'
    return render(request, 'profiles/edit.html', {'profile': profile, 'base_template': base_template})

@login_required
@require_POST
def quick_status_update(request):
    new_status = request.POST.get('status')
    is_auto = request.POST.get('is_auto') == '1'
    if new_status in ['online', 'idle', 'dnd', 'offline']:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        
        # If auto-idle or auto-online, only apply if user's manual preference is 'online'
        if is_auto:
            if profile.manual_status != 'online':
                return JsonResponse({
                    'status': 'ignored',
                    'status_setting': profile.status_setting,
                    'status_display': profile.get_status_setting_display()
                })
            profile.status_setting = new_status
        else:
            profile.manual_status = new_status
            profile.status_setting = new_status
            
        profile.save(update_fields=['status_setting', 'manual_status'])
        
        # Broadcast presence update via Channels
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "user_presence",
                    {
                        "type": "presence_update",
                        "user_id": request.user.id,
                        "username": request.user.username,
                        "status": profile.status_setting,
                        "status_display": profile.get_status_setting_display()
                    }
                )
        except Exception:
            pass
            
        return JsonResponse({
            'status': 'success',
            'status_setting': profile.status_setting,
            'status_display': profile.get_status_setting_display(),
            'manual_status': profile.manual_status,
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid status option.'}, status=400)

@login_required
def friends_list(request):
    from .models import Friendship, FriendRequest
    from chat.models import DirectMessageSession
    from django.db.models import Q
    
    friendships1 = Friendship.objects.filter(user1=request.user).select_related('user2', 'user2__profile')
    friendships2 = Friendship.objects.filter(user2=request.user).select_related('user1', 'user1__profile')
    
    friends = []
    for f in friendships1:
        friends.append(f.user2)
    for f in friendships2:
        friends.append(f.user1)
        
    received_requests = FriendRequest.objects.filter(receiver=request.user).select_related('sender', 'sender__profile')
    sent_requests = FriendRequest.objects.filter(sender=request.user).select_related('receiver', 'receiver__profile')
    
    dm_sessions = DirectMessageSession.objects.filter(Q(user1=request.user) | Q(user2=request.user)).order_by('-updated_at')
    
    # Auto-clear social ping when viewing friends
    request.session['clear_social_ping'] = True
    
    return render(request, 'profiles/friends.html', {
        'friends': friends,
        'received_requests': received_requests,
        'sent_requests': sent_requests,
        'dm_sessions': dm_sessions
    })

@login_required
def clear_social_ping(request):
    request.session['clear_social_ping'] = True
    return JsonResponse({'status': 'ok'})

@login_required
def send_friend_request_by_username(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        if username:
            target_user = User.objects.filter(username=username).first()
            if target_user and target_user != request.user:
                from .models import Friendship, FriendRequest
                # Check if they are already friends
                is_friend = Friendship.objects.filter(user1=request.user, user2=target_user).exists() or Friendship.objects.filter(user1=target_user, user2=request.user).exists()
                if not is_friend:
                    obj, created = FriendRequest.objects.get_or_create(sender=request.user, receiver=target_user)
                    if created:
                        from channels.layers import get_channel_layer
                        from asgiref.sync import async_to_sync
                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            f"user_notifications_{target_user.id}",
                            {
                                "type": "send_notification",
                                "payload": {
                                    "type": "friend_request",
                                    "title": f"New Friend Request",
                                    "message": f"{request.user.username} sent you a friend request.",
                                    "url": "/friends/"
                                }
                            }
                        )
    return redirect('friends')
