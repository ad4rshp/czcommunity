from asgiref.sync import sync_to_async
from django.utils import timezone
from .models import Channel, Message, Reaction, CommunityMember

class ChatService:
    @staticmethod
    async def create_message(channel_slug, user, content, embed_data=None, reply_to_id=None):
        try:
            channel = await Channel.objects.select_related('category__community').aget(slug=channel_slug)
            community = channel.category.community
            
            # Use async ORM for related objects — select_related avoids lazy loads in async
            membership = await CommunityMember.objects.select_related('community', 'user').filter(community=community, user=user).afirst()
            is_owner = (user.id == community.owner_id)
            
            # Check SEND_MESSAGES
            if not is_owner:
                if not membership:
                    return None, None
                has_send = await membership.ahas_permission('SEND_MESSAGES')
                if not has_send:
                    return None, None
            
            # Check EMBED_LINKS
            if embed_data and not is_owner:
                has_embed = await membership.ahas_permission('EMBED_LINKS')
                if not has_embed:
                    return None, None

            reply_to = None
            if reply_to_id:
                reply_to = await Message.objects.select_related('author', 'author__profile').filter(id=reply_to_id).afirst()

            message = await Message.objects.acreate(
                channel=channel,
                author=user,
                content=content,
                embed_data=embed_data,
                reply_to=reply_to
            )
            
            # Prepare payload
            from django.utils.html import escape
            
            # Re-fetch with select_related for payload data
            message = await Message.objects.select_related('author', 'author__profile', 'reply_to__author', 'reply_to__author__profile', 'channel__category__community').aget(id=message.id)
            author = message.author
            profile = getattr(author, 'profile', None)
            
            author_color = None
            if membership:
                highest_role = await membership.roles.exclude(name='@everyone').order_by('-position', '-id').afirst()
                if highest_role and highest_role.color:
                    author_color = highest_role.color

            author_display_name = membership.get_display_name() if membership else (author.display_name if hasattr(author, 'display_name') else author.username)

            reply_to_data = None
            if message.reply_to:
                rep_auth = message.reply_to.author
                rep_prof = getattr(rep_auth, 'profile', None)
                rep_membership = await CommunityMember.objects.select_related('user', 'community').filter(community=community, user=rep_auth).afirst()
                rep_display = rep_membership.get_display_name() if rep_membership else (rep_auth.display_name if hasattr(rep_auth, 'display_name') else rep_auth.username)
                reply_to_data = {
                    "id": message.reply_to.id,
                    "author": rep_auth.username,
                    "author_display_name": rep_display,
                    "content": escape(message.reply_to.content[:60]),
                    "avatar_url": rep_prof.get_avatar_url() if rep_prof else "/static/img/default_avatar.svg"
                }

            payload = {
                "type": "chat.message",
                "action": "message.created",
                "message_id": message.id,
                "content": escape(message.content),
                "author": author.username,
                "author_display_name": author_display_name,
                "author_uid": getattr(profile, 'unique_id', str(author.id)) if profile else str(author.id),
                "author_color": author_color,
                "created_at": message.created_at.strftime('%I:%M %p'),
                "avatar_url": profile.get_avatar_url() if profile else "/static/img/default_avatar.svg",
                "is_bot": profile.is_bot if profile else False,
                "embed_data": message.embed_data,
                "attachment_url": message.attachment.url if message.attachment else None,
                "raw_message_id": message.id,
                "reply_to": reply_to_data,
            }
            return message, payload
        except Exception as e:
            print(f"Error creating message: {e}")
            return None, None

    @staticmethod
    async def update_message(message_id, user, new_content):
        try:
            message = await Message.objects.aget(
                id=message_id,
                author=user,
                deleted_at__isnull=True
            )
            message.content = new_content
            message.edited_at = timezone.now()
            await message.asave()
            return message
        except Message.DoesNotExist:
            return None

    @staticmethod
    async def delete_message(message_id, user):
        try:
            message = await Message.objects.select_related('channel__category__community').aget(
                id=message_id,
                deleted_at__isnull=True
            )
            can_delete = (message.author_id == user.id)
            
            if not can_delete:
                membership = await CommunityMember.objects.filter(
                    community=message.channel.category.community,
                    user=user
                ).afirst()
                if membership:
                    can_delete = await sync_to_async(membership.has_permission)('MANAGE_MESSAGES')
            
            if can_delete:
                message.deleted_at = timezone.now()
                await message.asave()
                return True
            return False
        except Message.DoesNotExist:
            return False

    @staticmethod
    async def toggle_reaction(message_id, user, emoji):
        try:
            message = await Message.objects.aget(
                id=message_id,
                deleted_at__isnull=True
            )
            reaction, created = await Reaction.objects.aget_or_create(
                message=message, user=user, emoji=emoji
            )
            if not created:
                await reaction.adelete()

            count = await Reaction.objects.filter(message=message, emoji=emoji).acount()
            return count
        except Message.DoesNotExist:
            return None

    @staticmethod
    def get_official_community():
        """Returns the configured official community, without hardcoding or auto-creating any server."""
        from .models import Community
        from core.models import DashboardConfig

        try:
            config = DashboardConfig.load()
            if config.official_community:
                return config.official_community
        except Exception:
            pass

        return Community.objects.filter(is_verified=True).first()

    @staticmethod
    def get_or_create_official_community(owner=None):
        """Backwards-compatible alias: returns official community without hardcoded creation."""
        return ChatService.get_official_community()


