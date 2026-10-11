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
            
            # Automatically join official (verified) communities
            from chat.models import Community, CommunityMember, Role
            official_communities = Community.objects.filter(is_verified=True)
            for community in official_communities:
                member, created = CommunityMember.objects.get_or_create(community=community, user=user)
                if created:
                    everyone_role = Role.objects.filter(community=community, name="@everyone").first()
                    if everyone_role:
                        member.roles.add(everyone_role)
            
            return redirect('community')
    else:
        form = CustomUserCreationForm()
    return render(request, 'auth/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')
