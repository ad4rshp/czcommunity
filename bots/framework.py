import asyncio
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
import inspect

class Context:
    """
    Represents the context in which a command is being invoked.
    """
    def __init__(self, bot, message, author, channel, community):
        self.bot = bot
        self.message = message
        self.author = author
        self.channel = channel
        self.community = community
        self.guild = community  # Alias for compatibility

    async def send(self, content):
        """Sends a message to the destination channel."""
        from chat.models import Message
        
        @sync_to_async
        def create_msg():
            return Message.objects.create(
                channel=self.channel,
                author=self.bot.user,
                content=content
            )
        
        msg = await create_msg()
        
        # Broadcast via Channels
        channel_layer = get_channel_layer()
        
        @sync_to_async
        def get_avatar_url():
            if hasattr(self.bot.user, 'profile'):
                return self.bot.user.profile.get_avatar_url()
            return "/static/img/default_avatar.svg"
            
        avatar_url = await get_avatar_url()
        
        await channel_layer.group_send(
            f"chat_{self.channel.id}",
            {
                'type': 'chat_message',
                'message': content,
                'username': self.bot.user.username,
                'avatar_url': avatar_url,
                'message_id': msg.id,
                'created_at': msg.created_at.isoformat()
            }
        )

class Command:
    def __init__(self, func, name=None):
        self.func = func
        self.name = name or func.__name__
        
    async def invoke(self, ctx, *args):
        if inspect.iscoroutinefunction(self.func):
            await self.func(ctx, *args)
        else:
            # Run sync functions in a threadpool to not block the event loop
            await sync_to_async(self.func)(ctx, *args)

class Bot:
    """
    Represents a bot/in-app application that can receive events and process commands.
    """
    def __init__(self, command_prefix, user):
        self.command_prefix = command_prefix
        self.user = user # The Django User model instance this bot acts as
        self.commands = {}
        self.events = {}
        
    def command(self, name=None):
        """Decorator to register a new command."""
        def decorator(func):
            cmd = Command(func, name)
            self.commands[cmd.name] = cmd
            return cmd
        return decorator
        
    def event(self, func):
        """Decorator to register an event listener (like on_message)."""
        self.events[func.__name__] = func
        return func
        
    async def process_commands(self, message_obj, text_content):
        """Checks if a message is a command and executes it."""
        # Don't process commands from other bots or itself
        if hasattr(message_obj.author, 'profile') and message_obj.author.profile.is_bot:
            if message_obj.author == self.user:
                return
                
        if not text_content.startswith(self.command_prefix):
            return
            
        parts = text_content[len(self.command_prefix):].split()
        if not parts:
            return
            
        command_name = parts[0]
        args = parts[1:]
        
        if command_name in self.commands:
            # We need the community/guild object
            @sync_to_async
            def get_community():
                return message_obj.channel.category.community
                
            community = await get_community()
            ctx = Context(self, message_obj, message_obj.author, message_obj.channel, community)
            
            try:
                await self.commands[command_name].invoke(ctx, *args)
            except Exception as e:
                print(f"Error executing command {command_name}: {e}")
            
    async def dispatch(self, event_name, *args, **kwargs):
        """Dispatches an event to the registered event listener."""
        if event_name in self.events:
            func = self.events[event_name]
            try:
                if inspect.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    await sync_to_async(func)(*args, **kwargs)
            except Exception as e:
                print(f"Error in event {event_name}: {e}")

class BotRegistry:
    """
    Global registry to hold all active bots in the application.
    """
    def __init__(self):
        self.bots = []
        
    def register(self, bot):
        self.bots.append(bot)
        
    async def dispatch_message(self, message_obj, text_content):
        """Send a message to all bots to process commands and trigger on_message."""
        for bot in self.bots:
            await bot.dispatch('on_message', message_obj, text_content)
            await bot.process_commands(message_obj, text_content)

# Global registry instance
registry = BotRegistry()
