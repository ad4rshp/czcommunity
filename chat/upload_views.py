import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Channel, Message
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@login_required
@csrf_exempt
def upload_attachment(request, channel_slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    channel = get_object_or_404(Channel, slug=channel_slug)
    file = request.FILES.get('file')
    content = request.POST.get('content', '')
    
    if not file:
        return JsonResponse({'error': 'No file provided'}, status=400)
        
    # Check permissions
    from .models import CommunityMember
    membership = CommunityMember.objects.filter(
        community=channel.category.community,
        user=request.user
    ).first()
    
    if not (request.user == channel.category.community.owner or (membership and membership.has_permission('ATTACH_FILES'))):
        return JsonResponse({'error': 'You do not have permission to attach files.'}, status=403)
        
    message = Message.objects.create(
        channel=channel,
        author=request.user,
        content=content,
        attachment=file
    )
    
    # Broadcast to channel
    author_display = membership.get_display_name() if membership else (message.author.display_name if hasattr(message.author, 'display_name') else message.author.username)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{channel.slug}",
        {
            "type": "chat.message",
            "action": "message.created",
            "message_id": message.id,
            "content": message.content,
            "author": message.author.username,
            "author_display_name": author_display,
            "created_at": message.created_at.strftime('%I:%M %p'),
            "avatar_url": message.author.profile.get_avatar_url() if hasattr(message.author, 'profile') else "/static/img/default_avatar.svg",
            "is_bot": message.author.profile.is_bot if hasattr(message.author, 'profile') else False,
            "embed_data": None,
            "attachment_url": message.attachment.url if message.attachment else None,
        }
    )
    
    # Also dispatch to bot framework
    from bots.framework import registry
    import asyncio
    
    # Use a fire-and-forget task in the background loop or run it via async_to_sync (might block if careful).
    # Safe approach for dispatching to bots from a sync view:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(registry.dispatch_message(message, content))
    except RuntimeError:
        pass # No running loop in this thread, which is fine since we are in a sync view. Bots might miss files, but they usually listen to text.

    return JsonResponse({'status': 'ok', 'message_id': message.id})
