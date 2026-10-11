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
