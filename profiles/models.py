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
    dm_setting = models.CharField(max_length=20, choices=DM_CHOICES, default='everyone')
    status_setting = models.CharField(max_length=20, choices=STATUS_CHOICES, default='online')

    def __str__(self):
        return f"{self.user.username}'s Profile"

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
