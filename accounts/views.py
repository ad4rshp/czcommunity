from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
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
                from chat.services import ChatService
                from chat.models import CommunityMember, Role
                official = ChatService.get_or_create_official_community(owner=user)
                if official:
                    member, created = CommunityMember.objects.get_or_create(community=official, user=user)
                    everyone_role = Role.objects.filter(community=official, name="@everyone").first()
                    if everyone_role:
                        member.roles.add(everyone_role)
                    return redirect(f"/community/chat/?c={official.slug}")
            
            return redirect('community')
    else:
        form = CustomUserCreationForm()
    return render(request, 'auth/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

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
