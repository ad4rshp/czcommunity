from django.db import models
from django.contrib.auth.models import User

class Community(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_communities')
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='community_icons/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Community / Server"
        verbose_name_plural = "Communities / Servers"

    def __str__(self):
        return self.name

    def get_icon_url(self):
        try:
            if self.icon and self.icon.name:
                return self.icon.url
        except Exception:
            pass
        if self.is_verified:
            return "/static/img/chillzone_logo.svg"
        return "/static/img/default_server.svg"

class CommunityInvite(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='invites')
    code = models.CharField(max_length=20, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    max_uses = models.IntegerField(default=0, help_text="0 for unlimited")
    uses = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Invite Code"
        verbose_name_plural = "Invite Codes"

    def __str__(self):
        return self.code

class ChannelCategory(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    position = models.IntegerField(default=0)
    is_collapsed_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['position']
        verbose_name = "Channel Category"
        verbose_name_plural = "Channel Categories"

    def __str__(self):
        return self.name

class Channel(models.Model):
    category = models.ForeignKey(ChannelCategory, on_delete=models.CASCADE, related_name='channels')
    CHANNEL_TYPES = (
        ('text', 'Text Channel'),
        ('voice', 'Voice Channel'),
        ('announcement', 'Announcement Channel'),
        ('music', 'Music Channel'),
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    channel_type = models.CharField(max_length=50, choices=CHANNEL_TYPES, default='text')
    position = models.IntegerField(default=0)
    cooldown = models.IntegerField(default=0, help_text="Cooldown in seconds between messages")
    bitrate = models.IntegerField(default=64000, help_text="Bitrate for voice channels")
    user_limit = models.IntegerField(default=0, help_text="Maximum users in voice channel")
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def community(self):
        return self.category.community if self.category else None

    @property
    def bitrate_kbps(self):
        try:
            return int(self.bitrate) // 1000 if self.bitrate else 64
        except (ValueError, TypeError):
            return 64

    class Meta:
        ordering = ['position']
        verbose_name = "Channel"
        verbose_name_plural = "Channels"

    def __str__(self):
        return f"#{self.name}"

class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    embed_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)

    @property
    def author_display_name(self):
        if hasattr(self, '_author_display_name') and self._author_display_name:
            return self._author_display_name
        return self.author.display_name if hasattr(self.author, 'display_name') else self.author.username

    @author_display_name.setter
    def author_display_name(self, value):
        self._author_display_name = value

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['channel', 'created_at']),
        ]

    def __str__(self):
        return f"{self.author.username}: {self.content[:50]}"

class Reaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} on {self.message.id}"

class Role(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#99AAB5")
    position = models.IntegerField(default=0)
    display_separately = models.BooleanField(default=False)
    allow_mention = models.BooleanField(default=False)
    
    # Permissions
    MODERATE_MEMBERS = models.BooleanField(default=False)
    MANAGE_ROLES = models.BooleanField(default=False)
    MANAGE_NICKNAMES = models.BooleanField(default=False)
    CHANGE_NICKNAME = models.BooleanField(default=False)
    READ_MESSAGE_HISTORY = models.BooleanField(default=True)
    ATTACH_FILES = models.BooleanField(default=True)
    EMBED_LINKS = models.BooleanField(default=True)
    MANAGE_MESSAGES = models.BooleanField(default=False)
    SEND_MESSAGES = models.BooleanField(default=True)
    VIEW_CHANNEL = models.BooleanField(default=True)
    MANAGE_CHANNELS = models.BooleanField(default=False)
    KICK_MEMBERS = models.BooleanField(default=False)
    BAN_MEMBERS = models.BooleanField(default=False)
    ADMINISTRATOR = models.BooleanField(default=False)

    class Meta:
        ordering = ['-position']

    def __str__(self):
        return f"{self.name} ({self.community.name})"

class ChannelPermission(models.Model):
    """
    Overrides specific permissions for a Role or Member within a specific Channel.
    True = Granted, False = Denied, None = Inherit from Role
    """
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='permissions')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True, related_name='channel_permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='channel_user_permissions')
    
    # Permission Matrix (Nullable Boolean = True/False/Inherit)
    view_channel = models.BooleanField(null=True, blank=True, default=None)
    manage_channel = models.BooleanField(null=True, blank=True, default=None)
    manage_permissions = models.BooleanField(null=True, blank=True, default=None)
    send_messages = models.BooleanField(null=True, blank=True, default=None)
    send_embeds = models.BooleanField(null=True, blank=True, default=None)
    attach_files = models.BooleanField(null=True, blank=True, default=None)
    connect_voice = models.BooleanField(null=True, blank=True, default=None)
    speak_voice = models.BooleanField(null=True, blank=True, default=None)
    
    class Meta:
        verbose_name = "Channel Permission"
        verbose_name_plural = "Channel Permissions"
        
    def __str__(self):
        target = self.role.name if self.role else (self.user.username if self.user else "Unknown")
        return f"{target} perms for #{self.channel.name}"

class CommunityMember(models.Model):
    NOTIFICATION_LEVELS = [
        ('all', 'All Messages'),
        ('mentions', 'Only @mentions'),
        ('nothing', 'Nothing'),
    ]

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_memberships')
    nickname = models.CharField(max_length=50, blank=True, default="")
    roles = models.ManyToManyField(Role, blank=True, related_name='members')
    notification_level = models.CharField(max_length=20, choices=NOTIFICATION_LEVELS, default='all')
    suppress_everyone = models.BooleanField(default=False)
    suppress_roles = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('community', 'user')
        verbose_name = "Server Member"
        verbose_name_plural = "Server Members"

    def __str__(self):
        return f"{self.user.username} in {self.community.name}"

    def get_display_name(self):
        if self.nickname and self.nickname.strip():
            return self.nickname.strip()
        if hasattr(self.user, 'profile'):
            return self.user.profile.get_display_name()
        if self.user and self.user.first_name and self.user.first_name.strip():
            return self.user.first_name.strip()
        return self.user.username if self.user else "User"

    @property
    def highest_role(self):
        return self.roles.exclude(name__iexact='@everyone').order_by('-position', '-id').first()

    @property
    def role_color(self):
        hr = self.highest_role
        return hr.color if hr else None

    def has_permission(self, perm_name):
        # Owner has all permissions
        if self.user == self.community.owner:
            return True

        # Get roles (user roles + @everyone)
        roles_to_check = list(self.roles.all())
        from .roles import ensure_everyone_role
        roles_to_check.append(ensure_everyone_role(self.community_id))

        # Check roles
        for role in roles_to_check:
            # Never let a malformed duplicate default role become an admin escape hatch.
            if role.name.casefold() == "@everyone":
                if perm_name == 'ADMINISTRATOR':
                    continue
                if getattr(role, perm_name, False):
                    return True
                continue
            if getattr(role, 'ADMINISTRATOR', False):
                return True
            if getattr(role, perm_name, False):
                return True
        return False

    async def ahas_permission(self, perm_name):
        # Check if user is the community owner safely without triggering sync DB access
        is_owner = False
        if hasattr(self, '_state') and 'community' in getattr(self._state, 'fields_cache', {}):
            is_owner = (self.user_id == self.community.owner_id)
        else:
            comm_owner_id = await Community.objects.filter(id=self.community_id).values_list('owner_id', flat=True).afirst()
            is_owner = (self.user_id == comm_owner_id)
            
        if is_owner:
            return True
            
        roles_to_check = []
        async for role in self.roles.all():
            roles_to_check.append(role)
            
        everyone_role = await Role.objects.filter(
            community_id=self.community_id, name__iexact="@everyone"
        ).order_by('id').afirst()
        if everyone_role is None:
            everyone_role, _ = await Role.objects.aget_or_create(
                community_id=self.community_id,
                name="@everyone",
                defaults={'color': '#99AAB5', 'position': 0},
            )
        protected_fields = []
        if everyone_role.name != '@everyone':
            everyone_role.name = '@everyone'
            protected_fields.append('name')
        if everyone_role.ADMINISTRATOR:
            everyone_role.ADMINISTRATOR = False
            protected_fields.append('ADMINISTRATOR')
        if everyone_role.display_separately:
            everyone_role.display_separately = False
            protected_fields.append('display_separately')
        if everyone_role.allow_mention:
            everyone_role.allow_mention = False
            protected_fields.append('allow_mention')
        if protected_fields:
            await everyone_role.asave(update_fields=protected_fields)
        roles_to_check.append(everyone_role)

        for role in roles_to_check:
            if role.name.casefold() == "@everyone":
                if perm_name == 'ADMINISTRATOR':
                    continue
                if getattr(role, perm_name, False):
                    return True
                continue
            if getattr(role, 'ADMINISTRATOR', False):
                return True
            if getattr(role, perm_name, False):
                return True
        return False

class DirectMessageSession(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dm_sessions1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dm_sessions2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user1', 'user2')

class DirectMessage(models.Model):
    session = models.ForeignKey(DirectMessageSession, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='direct_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    @property
    def author_display_name(self):
        return self.author.display_name if hasattr(self.author, 'display_name') else self.author.username

class AuditLog(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.user} - {self.action} at {self.created_at}"

class CommunityBan(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='bans')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_bans')
    banned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bans_issued')
    reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('community', 'user')
        ordering = ['-created_at']
        verbose_name = "Community Ban"
        verbose_name_plural = "Community Bans"

    def __str__(self):
        return f"{self.user.username} banned from {self.community.name}"

class ChannelReadState(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_read_states')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='read_states')
    last_read_message_id = models.IntegerField(default=0)
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'channel')
        verbose_name = "Channel Read State"
        verbose_name_plural = "Channel Read States"

    def __str__(self):
        return f"{self.user.username} read #{self.channel.name} (last msg: {self.last_read_message_id})"
