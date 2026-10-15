def active_community(request):
    if request.user.is_authenticated:
        from chat.models import CommunityMember, ChannelReadState, Message, DirectMessageSession
        from profiles.models import FriendRequest
        from django.db.models import Q
        
        memberships = CommunityMember.objects.filter(user=request.user).select_related('community')
        user_communities = [m.community for m in memberships]
        
        # Calculate pending mentions for each server
        for comm in user_communities:
            read_states = dict(
                ChannelReadState.objects.filter(
                    user=request.user,
                    channel__category__community=comm
                ).values_list('channel_id', 'last_read_message_id')
            )
            
            mentions_qs = Message.objects.filter(
                channel__category__community=comm
            ).filter(
                Q(content__icontains=f"@{request.user.username}") |
                Q(content__contains="@everyone") |
                Q(content__contains="@here")
            ).exclude(author=request.user)
            
            unread_mentions = 0
            for m in mentions_qs.values('id', 'channel_id')[:50]:
                last_read = read_states.get(m['channel_id'], 0)
                if m['id'] > last_read:
                    unread_mentions += 1
            
            comm.pending_mentions_count = unread_mentions
        
        # Pending Social Count: pending friend requests (respects clear_social_ping flag)
        if request.session.get('clear_social_ping'):
            pending_social_count = 0
        else:
            pending_social_count = FriendRequest.objects.filter(receiver=request.user).count()
        
        active = None
        if request.path.startswith('/community/'):
            comm_slug = request.GET.get('c')
            if comm_slug:
                active = next((c for c in user_communities if c.slug == comm_slug), None)
            if not active and user_communities:
                active = user_communities[0]
            
        return {
            'user_communities': user_communities,
            'active_community': active,
            'pending_social_count': pending_social_count,
        }
    return {
        'user_communities': [],
        'active_community': None,
        'pending_social_count': 0,
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
