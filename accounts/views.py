from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q
from .forms import CustomUserCreationForm

def login_view(request):
    if request.user.is_authenticated:
        return redirect('community')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('community')
    else:
        form = AuthenticationForm()
    return render(request, 'auth/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('community')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            
            # Check if user opted in to join the official server
            join_official = form.cleaned_data.get('join_official', True)
            if join_official:
                from core.models import DashboardConfig
                from chat.models import Community, CommunityMember, Role
                config = DashboardConfig.load()
                official = config.official_community or Community.objects.filter(is_verified=True).first()
                if official:
                    member, created = CommunityMember.objects.get_or_create(community=official, user=user)
                    everyone_role = Role.objects.filter(community=official, name="@everyone").first()
                    if everyone_role:
                        member.roles.add(everyone_role)
                    return redirect(f"/community/chat/?c={official.slug}")
                elif config.official_invite_link:
                    invite_target = config.official_invite_link.strip()
                    if invite_target:
                        return redirect(invite_target)
            
            return redirect('friends')
    else:
        form = CustomUserCreationForm()
    return render(request, 'auth/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

def recover_account_view(request):
    """
    Zero-Cost Account Recovery & Anti-Hack Password Reset:
    Enables users whose accounts were compromised or passwords forgotten
    to reset password and terminate sessions globally across all devices
    using their secret Personal Recovery Key or Admin Emergency PIN,
    without requiring expensive third-party email APIs.
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    from profiles.models import Profile
    import secrets
    import string

    error_msg = None
    success_data = None

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        recovery_secret = request.POST.get('recovery_secret', '').strip().upper()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not identifier:
            error_msg = "Please enter your Username, Email, or Unique ID."
        elif not recovery_secret:
            error_msg = "Please enter your Personal Security Recovery Key or Admin Emergency PIN."
        elif not new_password:
            error_msg = "Please enter a new password."
        elif new_password != confirm_password:
            error_msg = "The two passwords do not match. Please re-enter."
        elif len(new_password) < 8:
            error_msg = "Password must be at least 8 characters long."
        else:
            # 1. Find User by username, email, or Unique ID
            user = User.objects.filter(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            ).first()

            if not user:
                uid_cand = identifier.upper()
                if not uid_cand.startswith("CZ-") and uid_cand.isalnum():
                    uid_alt = f"CZ-{uid_cand}"
                else:
                    uid_alt = uid_cand
                user = User.objects.filter(
                    Q(profile__unique_id__iexact=uid_cand) |
                    Q(profile__unique_id__iexact=uid_alt)
                ).first()

            if not user:
                error_msg = f"No account found matching '{identifier}'. Check your username, email, or Unique ID."
            else:
                profile = getattr(user, 'profile', None)
                if not profile:
                    profile = Profile.objects.create(user=user)

                # 2. Verify Recovery Key or Emergency PIN
                stored_key = (profile.recovery_key or '').strip().upper()
                stored_pin = (profile.emergency_pin or '').strip().upper()
                is_pin_valid = False
                if stored_pin and profile.emergency_pin_expires_at:
                    if timezone.now() <= profile.emergency_pin_expires_at:
                        if recovery_secret == stored_pin:
                            is_pin_valid = True

                is_key_valid = (recovery_secret == stored_key and bool(stored_key))

                if not (is_key_valid or is_pin_valid):
                    error_msg = "Invalid Recovery Key or Emergency PIN. If your account was hacked and you lost your key, please contact a ChillZone Admin with your Unique ID."
                else:
                    # 3. Validated! Reset password
                    user.set_password(new_password)
                    user.save()

                    # 4. Global Multi-Device Logout (Invalidate all active sessions across all devices)
                    user_id_str = str(user.id)
                    purged_count = 0
                    for s in Session.objects.filter(expire_date__gte=timezone.now()):
                        try:
                            data = s.get_decoded()
                            if str(data.get('_auth_user_id')) == user_id_str:
                                s.delete()
                                purged_count += 1
                        except Exception:
                            pass

                    # 5. Rotate Recovery Key & clear emergency PIN (Invalidates compromised key)
                    chars = string.ascii_uppercase + string.digits
                    c1 = ''.join(secrets.choice(chars) for _ in range(4))
                    c2 = ''.join(secrets.choice(chars) for _ in range(4))
                    c3 = ''.join(secrets.choice(chars) for _ in range(4))
                    new_recovery_key = f"CZ-REC-{c1}-{c2}-{c3}"
                    profile.recovery_key = new_recovery_key
                    profile.emergency_pin = ""
                    profile.emergency_pin_expires_at = None
                    profile.save()

                    success_data = {
                        'username': user.username,
                        'unique_id': profile.unique_id,
                        'new_recovery_key': new_recovery_key,
                        'purged_count': purged_count,
                    }

    return render(request, 'auth/recover.html', {
        'error_msg': error_msg,
        'success_data': success_data,
    })

@login_required
def logout_all_devices_view(request):
    """Logs out user across all other sessions/devices while preserving or restarting session."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    from django.contrib import messages

    if request.method == 'POST':
        user_id_str = str(request.user.id)
        current_session_key = request.session.session_key
        purged = 0
        for s in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                data = s.get_decoded()
                if str(data.get('_auth_user_id')) == user_id_str and s.session_key != current_session_key:
                    s.delete()
                    purged += 1
            except Exception:
                pass
        messages.success(request, f"Terminated {purged} other active sessions across all devices.")
    return redirect('/profiles/edit/?tab=account')

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Report, Block
from chat.models import Message
from django.contrib.auth.models import User

@login_required
def report_message(request):
    if request.method == 'POST':
        message_id = request.POST.get('message_id')
        reason = request.POST.get('reason', 'other')
        details = request.POST.get('details', '')
        
        message = Message.objects.filter(id=message_id).select_related('author').first()
        if not message:
            return JsonResponse({'status': 'error', 'message': 'Message not found'}, status=404)
            
        Report.objects.create(
            reporter=request.user,
            reported_user=message.author,
            reason=reason,
            details=f"Message ID {message.id}: \"{message.content[:200]}\". Details: {details}"
        )
        return JsonResponse({'status': 'success', 'message': 'Report submitted to moderators successfully!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

@login_required
def toggle_block_user(request, username):
    if request.method == 'POST':
        target = User.objects.filter(username__iexact=username).first()
        if not target:
            return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
        if target == request.user:
            return JsonResponse({'status': 'error', 'message': 'You cannot block yourself'}, status=400)
            
        existing = Block.objects.filter(blocker=request.user, blocked=target).first()
        if existing:
            existing.delete()
            return JsonResponse({'status': 'unblocked', 'message': f'Unblocked @{target.username}'})
        else:
            Block.objects.create(blocker=request.user, blocked=target)
            return JsonResponse({'status': 'blocked', 'message': f'Blocked @{target.username}'})
            
    # GET: check block status
    target = User.objects.filter(username__iexact=username).first()
    is_blocked = Block.objects.filter(blocker=request.user, blocked=target).exists() if target else False
    return JsonResponse({'status': 'success', 'is_blocked': is_blocked})
