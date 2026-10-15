from asgiref.sync import sync_to_async
from django.utils import timezone
from .models import Channel, Message, Reaction, CommunityMember

class ChatService:
    @staticmethod
    async def create_message(channel_slug, user, content, embed_data=None):
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

            message = await Message.objects.acreate(
                channel=channel,
                author=user,
                content=content,
                embed_data=embed_data
            )
            
            # Prepare payload
            from django.utils.html import escape
            
            # Re-fetch with select_related for payload data
            message = await Message.objects.select_related('author', 'author__profile').aget(id=message.id)
            author = message.author
            profile = getattr(author, 'profile', None)
            
            author_color = None
            if membership:
                highest_role = await membership.roles.exclude(name='@everyone').order_by('-position', '-id').afirst()
                if highest_role and highest_role.color:
                    author_color = highest_role.color

            payload = {
                "type": "chat.message",
                "action": "message.created",
                "message_id": message.id,
                "content": escape(message.content),
                "author": author.username,
                "author_color": author_color,
                "created_at": message.created_at.strftime('%I:%M %p'),
                "avatar_url": profile.get_avatar_url() if profile else "/static/img/default_avatar.svg",
                "is_bot": profile.is_bot if profile else False,
                "embed_data": message.embed_data,
                "attachment_url": message.attachment.url if message.attachment else None,
                "raw_message_id": message.id,
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
    def get_or_create_official_community(owner=None):
        from .models import Community, ChannelCategory, Channel, Role, CommunityMember
        from django.contrib.auth.models import User

        official = Community.objects.filter(is_verified=True).first()
        if not official:
            official = Community.objects.filter(slug='official-chillzone').first()
            if official and not official.is_verified:
                official.is_verified = True
                official.save(update_fields=['is_verified'])

        if not official:
            if not owner:
                owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not owner:
                return None

            official, _ = Community.objects.get_or_create(
                slug='official-chillzone',
                defaults={
                    'name': 'Chillzone Official',
                    'owner': owner,
                    'description': 'The official verified Chillzone server for announcements, hanging out, and voice channels.',
                    'is_verified': True,
                }
            )

            everyone_role, _ = Role.objects.get_or_create(
                community=official,
                name='@everyone',
                defaults={'position': 0, 'color': '#99AAB5'}
            )

            welcome_cat, _ = ChannelCategory.objects.get_or_create(
                community=official,
                name='Welcome',
                defaults={'slug': 'official-welcome', 'position': 0}
            )

            Channel.objects.get_or_create(
                category=welcome_cat,
                name='general',
                defaults={'slug': 'official-general', 'channel_type': 'text', 'position': 0}
            )

            Channel.objects.get_or_create(
                category=welcome_cat,
                name='General Voice',
                defaults={'slug': 'official-general-voice', 'channel_type': 'voice', 'position': 1}
            )

            if owner:
                owner_member, _ = CommunityMember.objects.get_or_create(community=official, user=owner)
                owner_member.roles.add(everyone_role)

        return official

