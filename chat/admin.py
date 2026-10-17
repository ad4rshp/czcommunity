
from django.contrib import admin
from .models import Community, ChannelCategory, Channel, Message, Reaction, Role, CommunityMember, DirectMessageSession, DirectMessage, AuditLog

@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'owner', 'created_at')
    search_fields = ('name', 'slug', 'owner__username')
    list_filter = ('created_at',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(ChannelCategory)
class ChannelCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'community', 'position')
    list_filter = ('community',)
    search_fields = ('name', 'community__name')
    ordering = ('community', 'position')

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'channel_type', 'position')
    list_filter = ('channel_type', 'category__community')
    search_fields = ('name', 'category__community__name')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'channel', 'created_at')
    list_filter = ('channel__category__community', 'created_at')
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at', 'edited_at', 'deleted_at')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'community', 'position', 'color')
    list_filter = ('community',)
    search_fields = ('name',)

@admin.register(CommunityMember)
class CommunityMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'joined_at')
    list_filter = ('community', 'joined_at')
    search_fields = ('user__username', 'community__name')

@admin.register(DirectMessageSession)
class DirectMessageSessionAdmin(admin.ModelAdmin):
    list_display = ('user1', 'user2', 'updated_at')
    search_fields = ('user1__username', 'user2__username')

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('author', 'session', 'created_at')
    search_fields = ('content', 'author__username')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'community', 'created_at')
    list_filter = ('community', 'action', 'created_at')
    search_fields = ('action', 'details', 'user__username', 'community__name')
    readonly_fields = ('created_at',)


