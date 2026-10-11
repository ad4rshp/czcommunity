from django.contrib import admin
from .models import Profile, FriendRequest, Friendship

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_bot', 'status_setting', 'dm_setting')
    list_filter = ('is_bot', 'status_setting', 'dm_setting')
    search_fields = ('user__username', 'bio', 'favorite_game')

@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'created_at')
    search_fields = ('sender__username', 'receiver__username')
    list_filter = ('created_at',)

@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('user1', 'user2', 'created_at')
    search_fields = ('user1__username', 'user2__username')
    list_filter = ('created_at',)
