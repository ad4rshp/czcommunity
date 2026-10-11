import json
import re
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils.html import escape
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Channel, Message, Reaction, DirectMessage, DirectMessageSession
from .services import ChatService

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
            return
            
        self.user_group_name = f"user_notifications_{self.scope['user'].id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event["payload"]))


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.channel_slug = self.scope["url_route"]["kwargs"]["channel_slug"]
        self.room_group_name = f"chat_{self.channel_slug}"

        self.last_message_time = None
        self.last_message_content = None

        if self.scope["user"].is_anonymous:
            await self.close()
            return

        # Check if channel exists and get its cooldown
        self.channel_cooldown = await self.get_channel_cooldown(self.channel_slug)
        if self.channel_cooldown is None:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        action = text_data_json.get("action")

        if action == "message.create":
            message_content = text_data_json.get("content", "")
            embed_data = text_data_json.get("embed_data", None)
            
            if message_content.strip() or embed_data:
                now = timezone.now()
                # Anti-spam check
                if self.last_message_time:
                    channel_cd = self.channel_cooldown or 0
                    if channel_cd > 0 and (now - self.last_message_time).total_seconds() < channel_cd:
                        await self.send(text_data=json.dumps({
                            "type": "chat.error",
                            "message": f"Please wait {channel_cd} seconds before sending another message."
                        }))
                        return  
                    elif (now - self.last_message_time).total_seconds() < 0.2:
                        return  # Prevent rapid double-clicks

                self.last_message_time = now
                self.last_message_content = message_content.strip()

                # Save message to DB via ChatService
                result = await ChatService.create_message(self.channel_slug, self.scope["user"], message_content, embed_data)
                if result:
                    message, payload = result
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        payload
                    )
                    
                    # Send mention notifications
                    mentioned_usernames = re.findall(r'@([\w]+)', message_content)
                    if mentioned_usernames:
                        users = await self.get_users_by_usernames(mentioned_usernames)
                        for u in users:
                            if u.id != self.scope["user"].id:
                                await self.channel_layer.group_send(
                                    f"user_notifications_{u.id}",
                                    {
                                        "type": "send_notification",
                                        "payload": {
                                            "type": "mention",
                                            "title": f"New mention from {self.scope['user'].username}",
                                            "message": message_content[:50] + ("..." if len(message_content) > 50 else ""),
                                            "url": f"/community/chat/?c={message.channel.community.slug}&channel={message.channel.name}"
                                        }
                                    }
                                )
                    
                    # Dispatch to bot framework
                    import asyncio
                    from bots.framework import registry
                    asyncio.create_task(registry.dispatch_message(message, message_content))
        elif action == "message.update":
            message_id = text_data_json.get("message_id")
            new_content = text_data_json.get("content", "")
            if message_id and new_content.strip():
                updated_message = await ChatService.update_message(
                    message_id, self.scope["user"], new_content
                )
                if updated_message:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "chat.message",
                            "action": "message.updated",
                            "message_id": updated_message.id,
                            "content": escape(updated_message.content)
                        }
                    )
        elif action == "message.delete":
            message_id = text_data_json.get("message_id")
            if message_id:
                deleted = await ChatService.delete_message(message_id, self.scope["user"])
                if deleted:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "chat.message",
                            "action": "message.deleted",
                            "message_id": message_id
                        }
                    )
        elif action == "message.react":
            message_id = text_data_json.get("message_id")
            emoji = text_data_json.get("emoji", "❤️")
            if message_id:
                reaction_count = await ChatService.toggle_reaction(message_id, self.scope["user"], emoji)
                if reaction_count is not None:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "chat.message",
                            "action": "message.reacted",
                            "message_id": message_id,
                            "emoji": emoji,
                            "count": reaction_count
                        }
                    )
        elif action == "typing.started" or action == "typing.stopped":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat.typing",
                    "action": action,
                    "author": self.scope["user"].username,
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_typing(self, event):
        if event["author"] != self.scope["user"].username:
            await self.send(text_data=json.dumps(event))

    @sync_to_async
    def get_channel_cooldown(self, slug):
        channel = Channel.objects.filter(slug=slug).first()
        if channel:
            return channel.cooldown
        return None
        
    @sync_to_async
    def get_users_by_usernames(self, usernames):
        from django.contrib.auth.models import User
        return list(User.objects.filter(username__in=usernames))



class DirectMessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'dm_{self.session_id}'
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        content = data.get('content', '')

        if action == 'message.create':
            payload = await self.create_message_payload(self.session_id, self.user, content)
            if payload:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    payload
                )
                
                # Send notification to the other user
                target_user_id = await self.get_target_user_id(self.session_id, self.user)
                if target_user_id:
                    await self.channel_layer.group_send(
                        f"user_notifications_{target_user_id}",
                        {
                            "type": "send_notification",
                            "payload": {
                                "type": "dm",
                                "title": f"New message from {self.user.username}",
                                "message": content[:50] + ("..." if len(content) > 50 else ""),
                                "url": f"/friends/dm/{self.user.username}/"
                            }
                        }
                    )
        elif action == 'message.update':
            message_id = data.get('message_id')
            updated_msg = await self.update_message(message_id, self.user, content)
            if updated_msg:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'action': 'message.updated',
                        'message_id': message_id,
                        'content': content
                    }
                )
        elif action == 'message.delete':
            message_id = data.get('message_id')
            success = await self.delete_message(message_id, self.user)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'action': 'message.deleted',
                        'message_id': message_id
                    }
                )
        elif action == 'typing.started' or action == 'typing.stopped':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'action': action,
                    'author': self.user.username
                }
            )

    async def chat_message(self, event):
        if event.get('action') in ('typing.started', 'typing.stopped') and event.get('author') == self.user.username:
            return
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def create_message_payload(self, session_id, author, content):
        session = DirectMessageSession.objects.get(id=session_id)
        message = DirectMessage.objects.create(session=session, author=author, content=content)
        profile = getattr(author, 'profile', None)
        return {
            'type': 'chat_message',
            'action': 'message.created',
            'message_id': message.id,
            'content': message.content,
            'author': author.username,
            'avatar_url': profile.get_avatar_url() if profile else '/static/img/default_avatar.svg',
            'created_at': message.created_at.strftime('%I:%M %p')
        }

    @sync_to_async
    def get_target_user_id(self, session_id, current_user):
        try:
            session = DirectMessageSession.objects.get(id=session_id)
            if session.user1 == current_user:
                return session.user2.id
            return session.user1.id
        except DirectMessageSession.DoesNotExist:
            return None

    @sync_to_async
    def update_message(self, message_id, author, content):
        try:
            msg = DirectMessage.objects.get(id=message_id, author=author)
            msg.content = content
            msg.edited_at = timezone.now()
            msg.save()
            return msg
        except DirectMessage.DoesNotExist:
            return None

    @sync_to_async
    def delete_message(self, message_id, author):
        try:
            msg = DirectMessage.objects.get(id=message_id, author=author)
            msg.delete()
            return True
        except DirectMessage.DoesNotExist:
            return False
