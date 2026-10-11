def active_community(request):
    if request.user.is_authenticated:
        from chat.models import CommunityMember
        memberships = CommunityMember.objects.filter(user=request.user).select_related('community')
        user_communities = [m.community for m in memberships]
        
        active = None
        if request.path.startswith('/community/'):
            active = user_communities[0] if user_communities else None
            
        return {
            'user_communities': user_communities,
            'active_community': active
        }
    return {
        'user_communities': [],
        'active_community': None
    }

def global_settings(request):
    try:
        from core.models import DashboardConfig
        settings = DashboardConfig.load()
    except Exception:
        settings = None
    return {
        'site_settings': settings
    }
