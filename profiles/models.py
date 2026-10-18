import secrets
import string
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    favorite_game = models.CharField(max_length=100, blank=True)
    is_bot = models.BooleanField(default=False)

    DM_CHOICES = [
        ('everyone', 'Everyone'),
        ('friends', 'Friends Only'),
        ('noone', 'No One'),
    ]
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('idle', 'Idle'),
        ('dnd', 'Do Not Disturb'),
        ('offline', 'Invisible'),
    ]
    display_name = models.CharField(max_length=50, blank=True, default="")
    dm_setting = models.CharField(max_length=20, choices=DM_CHOICES, default='everyone')
    status_setting = models.CharField(max_length=20, choices=STATUS_CHOICES, default='online')
    manual_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='online')
    unique_id = models.CharField(max_length=24, unique=True, null=True, blank=True, db_index=True, verbose_name='User ID')
    recovery_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    emergency_pin = models.CharField(max_length=12, blank=True, default="")
    emergency_pin_expires_at = models.DateTimeField(null=True, blank=True)

    def get_display_name(self):
        if self.display_name and self.display_name.strip():
            return self.display_name.strip()
        if self.user and self.user.first_name and self.user.first_name.strip():
            return self.user.first_name.strip()
        return self.user.username if self.user else "User"

    def save(self, *args, **kwargs):
        if not self.unique_id:
            for _ in range(10):
                num = secrets.randbelow(900000) + 100000
                cand = f"CZ-{num}"
                if not Profile.objects.filter(unique_id=cand).exists():
                    self.unique_id = cand
                    break
            if not self.unique_id:
                user_id_val = self.user_id or 1
                self.unique_id = f"CZ-{user_id_val:06d}"

        if not self.recovery_key:
            chars = string.ascii_uppercase + string.digits
            c1 = ''.join(secrets.choice(chars) for _ in range(4))
            c2 = ''.join(secrets.choice(chars) for _ in range(4))
            c3 = ''.join(secrets.choice(chars) for _ in range(4))
            self.recovery_key = f"CZ-REC-{c1}-{c2}-{c3}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Profile ({self.unique_id or 'No User ID'})"

    def get_avatar_url(self):
        try:
            if self.avatar and self.avatar.name:
                return self.avatar.url
        except Exception:
            pass
        palette = ['orange', 'blue', 'green', 'purple', 'pink', 'yellow']
        val = sum(ord(c) for c in (self.user.username if self.user else 'chillzone'))
        color = palette[val % len(palette)]
        return f"/static/img/default_avatar_{color}.svg"

class FriendRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}"

class Friendship(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"{self.user1.username} & {self.user2.username}"

def user_get_display_name(self):
    try:
        if hasattr(self, 'profile') and self.profile.display_name and self.profile.display_name.strip():
            return self.profile.display_name.strip()
    except Exception:
        pass
    if self.first_name and self.first_name.strip():
        return self.first_name.strip()
    return self.username

if not hasattr(User, 'display_name'):
    User.add_to_class('get_display_name', user_get_display_name)
    User.add_to_class('display_name', property(user_get_display_name))
