"""Shared community and channel permission checks."""

from django.db.models import Q

from accounts.models import Block
from profiles.models import Friendship, Profile

from .models import (
    ChannelPermission,
    CommunityMember,
    DirectMessageSession,
    Role,
)


def _membership_for(user, channel):
    return (
        CommunityMember.objects.filter(
            community_id=channel.category.community_id,
            user_id=user.id,
        )
        .select_related("community", "user")
        .prefetch_related("roles")
        .first()
    )


def _channel_override(user, channel, membership, field_name):
    user_override = ChannelPermission.objects.filter(
        channel_id=channel.id, user_id=user.id
    ).values_list(field_name, flat=True).first()
    if user_override is not None:
        return user_override

    role_ids = set()
    if membership:
        role_ids.update(membership.roles.values_list("id", flat=True))
    everyone_id = Role.objects.filter(
        community_id=channel.category.community_id, name="@everyone"
    ).order_by('id').values_list("id", flat=True).first()
    if everyone_id:
        role_ids.add(everyone_id)

    if not role_ids:
        return None

    role_overrides = list(
        ChannelPermission.objects.filter(
            channel_id=channel.id,
            role_id__in=role_ids,
            role__community_id=channel.category.community_id,
        )
        .exclude(**{f"{field_name}__isnull": True})
        .values_list(field_name, flat=True)
    )
    if False in role_overrides:
        return False
    if True in role_overrides:
        return True
    return None


def can_user_view_channel(user, channel, membership=None):
    """Return whether a user can see a channel, including private overrides."""
    community = channel.category.community
    if not getattr(user, "is_authenticated", False):
        return False
    if user.id == community.owner_id:
        return True

    membership = membership or _membership_for(user, channel)
    if not membership:
        return False
    if membership.has_permission("ADMINISTRATOR"):
        return True

    override = _channel_override(user, channel, membership, "view_channel")
    if override is not None:
        return override
    if channel.is_private:
        return False
    return membership.has_permission("VIEW_CHANNEL")


def can_user_perform_channel_action(
    user,
    channel,
    channel_permission,
    community_permission,
    membership=None,
):
    """Check channel visibility and then the channel-specific action override."""
    if not can_user_view_channel(user, channel, membership=membership):
        return False

    community = channel.category.community
    if user.id == community.owner_id:
        return True

    membership = membership or _membership_for(user, channel)
    if not membership:
        return False
    if membership.has_permission("ADMINISTRATOR"):
        return True

    override = _channel_override(
        user, channel, membership, channel_permission
    )
    if override is not None:
        return override
    return membership.has_permission(community_permission)


def get_dm_session_for_user(session_id, user):
    """Return a DM session only to one of its two participants."""
    try:
        session = DirectMessageSession.objects.select_related(
            "user1", "user2"
        ).get(id=session_id)
    except (DirectMessageSession.DoesNotExist, TypeError, ValueError):
        return None
    if user.id not in (session.user1_id, session.user2_id):
        return None
    return session


def can_send_dm(session, sender):
    """Honor blocks and the recipient's direct-message privacy setting."""
    if sender.id not in (session.user1_id, session.user2_id):
        return False

    recipient_id = (
        session.user2_id if sender.id == session.user1_id else session.user1_id
    )
    if Block.objects.filter(
        Q(blocker_id=sender.id, blocked_id=recipient_id)
        | Q(blocker_id=recipient_id, blocked_id=sender.id)
    ).exists():
        return False

    recipient_profile = Profile.objects.filter(user_id=recipient_id).first()
    dm_setting = recipient_profile.dm_setting if recipient_profile else "everyone"
    if dm_setting == "noone":
        return False
    if dm_setting == "friends" and not Friendship.objects.filter(
        Q(user1_id=sender.id, user2_id=recipient_id)
        | Q(user1_id=recipient_id, user2_id=sender.id)
    ).exists():
        return False
    return True
