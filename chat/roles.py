"""Shared helpers for the default role and role hierarchy."""

from django.db.models import Max, Min

from .models import Role


def ensure_everyone_role(community):
    """Repair communities that predate the required default role."""
    community_id = getattr(community, 'pk', community)
    role = Role.objects.filter(
        community_id=community_id, name__iexact='@everyone'
    ).order_by('id').first()
    if role is None:
        role = Role.objects.create(
            community_id=community_id,
            name='@everyone',
            color='#99AAB5',
            position=0,
        )
    changed_fields = []
    if role.name != '@everyone':
        role.name = '@everyone'
        changed_fields.append('name')
    if role.ADMINISTRATOR:
        role.ADMINISTRATOR = False
        changed_fields.append('ADMINISTRATOR')
    if role.display_separately:
        role.display_separately = False
        changed_fields.append('display_separately')
    if role.allow_mention:
        role.allow_mention = False
        changed_fields.append('allow_mention')
    if changed_fields:
        role.save(update_fields=changed_fields)
    return role


def ensure_member_default_role(member):
    """Attach the community default role to an existing or new membership."""
    if member and member.pk:
        member.roles.add(ensure_everyone_role(member.community_id))
    return member


def is_role_administrator(user, community, membership=None):
    if user.is_superuser or user.id == community.owner_id:
        return True
    return bool(membership and membership.has_permission('ADMINISTRATOR'))


def role_management_limit(membership):
    highest_role = membership.roles.exclude(name__iexact='@everyone').order_by(
        '-position', '-id'
    ).first()
    return highest_role.position if highest_role else 0


def can_manage_role(user, community, membership, role):
    if is_role_administrator(user, community, membership):
        return True
    if not membership or not membership.has_permission('MANAGE_ROLES'):
        return False
    if role.name.casefold() == '@everyone' or role.ADMINISTRATOR:
        return False
    return role.position < role_management_limit(membership)


def manageable_roles(user, community, membership):
    roles = Role.objects.filter(community=community)
    if is_role_administrator(user, community, membership):
        return roles
    if not membership or not membership.has_permission('MANAGE_ROLES'):
        return roles.none()
    return roles.filter(position__lt=role_management_limit(membership)).exclude(
        name__iexact='@everyone'
    ).exclude(ADMINISTRATOR=True)


def next_role_position(community, user, membership):
    if is_role_administrator(user, community, membership):
        highest = Role.objects.filter(community=community).aggregate(
            Max('position')
        )['position__max']
        return (highest or 0) + 1

    limit = role_management_limit(membership)
    lowest_manageable = Role.objects.filter(
        community=community, position__lt=limit
    ).aggregate(Min('position'))['position__min']
    return (lowest_manageable - 1) if lowest_manageable is not None else limit - 1
