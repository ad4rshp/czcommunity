from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from asgiref.sync import async_to_sync
from chat.models import Community, ChannelCategory, Channel, CommunityMember, Role, CommunityInvite, CommunityBan
from chat.models import ChannelPermission, DirectMessageSession, Message
from chat.forms import ChannelForm, CategoryForm
from chat.permissions import (
    can_send_dm,
    can_user_perform_channel_action,
    can_user_view_channel,
    get_dm_session_for_user,
)
from chat.services import ChatService
from accounts.models import Block
from profiles.models import Friendship

class SecurityAndRoutingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='server_owner', password='password123')
        self.member = User.objects.create_user(username='regular_member', password='password123')
        self.community = Community.objects.create(name='Test Hub', slug='test-hub', owner=self.owner)
        self.category = ChannelCategory.objects.create(name='General Categories', community=self.community)
        self.channel = Channel.objects.create(
            name='general-chat', slug='general-chat', category=self.category, channel_type='text'
        )
        self.voice_channel = Channel.objects.create(
            name='Voice Lounge', slug='voice-lounge', category=self.category, channel_type='voice'
        )
        
        # Add members
        CommunityMember.objects.create(community=self.community, user=self.owner)
        CommunityMember.objects.create(community=self.community, user=self.member)
        
        self.client_owner = Client()
        self.client_owner.login(username='server_owner', password='password123')
        
        self.client_member = Client()
        self.client_member.login(username='regular_member', password='password123')

    def test_async_message_creation_loads_profile_for_display_names(self):
        earlier = Message.objects.create(
            channel=self.channel, author=self.owner, content='Earlier message'
        )

        message, payload = async_to_sync(ChatService.create_message)(
            self.channel.slug,
            self.owner,
            'Message payload should be created',
            reply_to_id=earlier.id,
        )

        self.assertIsNotNone(message)
        self.assertEqual(payload['author_display_name'], self.owner.username)
        self.assertEqual(payload['reply_to']['author_display_name'], self.owner.username)

    @override_settings(DEBUG=False)
    def test_p0_production_404_page_does_not_leak_internals(self):
        """Verify that invalid URLs return safe 404 without leaking URLconf or DEBUG details."""
        response = self.client.get('/definitely-nonexistent-url-404-check/')
        self.assertEqual(response.status_code, 404)
        content = response.content.decode('utf-8')
        # Check custom safe page elements
        self.assertIn("Page Not Found", content)
        # Ensure debug details are NOT leaked
        self.assertNotIn("Using the URLconf defined in", content)
        self.assertNotIn("The current path, definitely-nonexistent-url", content)
        self.assertNotIn("DEBUG = True", content)

    def test_p1_category_management_routing(self):
        """Verify dynamic category routing loads and is not captured by channel slug."""
        url_manage = reverse('manage_category', kwargs={'category_id': self.category.id})
        url_add = reverse('add_channel', kwargs={'category_id': self.category.id})
        
        # Owner should load manage category
        resp_manage = self.client_owner.get(url_manage)
        self.assertEqual(resp_manage.status_code, 200)
        self.assertIn(self.category.name.upper(), resp_manage.content.decode('utf-8'))
        
        # Owner should load add channel in category
        resp_add = self.client_owner.get(url_add)
        self.assertEqual(resp_add.status_code, 200)

    def test_p1_unauthorized_category_and_channel_actions_return_403(self):
        """Verify regular members without permissions are blocked with 403."""
        url_manage = reverse('manage_category', kwargs={'category_id': self.category.id})
        url_add = reverse('add_channel', kwargs={'category_id': self.category.id})
        url_edit_channel = reverse('edit_channel', kwargs={'channel_slug': self.channel.slug})
        url_perms = reverse('get_channel_permissions', kwargs={'channel_slug': self.channel.slug})
        
        resp_manage = self.client_member.get(url_manage)
        self.assertEqual(resp_manage.status_code, 403)
        
        resp_add = self.client_member.get(url_add)
        self.assertEqual(resp_add.status_code, 403)
        
        resp_edit = self.client_member.get(url_edit_channel)
        self.assertEqual(resp_edit.status_code, 403)
        
        resp_perms = self.client_member.get(url_perms)
        self.assertEqual(resp_perms.status_code, 403)

    def test_p1_channel_form_validation(self):
        """Verify channel validation rejects blank names, trims whitespace, and validates numeric bounds."""
        # Empty name
        f1 = ChannelForm(data={'name': '   ', 'channel_type': 'text'})
        self.assertFalse(f1.is_valid())
        self.assertIn('name', f1.errors)

        # Negative cooldown
        f2 = ChannelForm(data={'name': 'chat', 'channel_type': 'text', 'cooldown': -5})
        self.assertFalse(f2.is_valid())
        self.assertIn('cooldown', f2.errors)

        # Negative user limit
        f3 = ChannelForm(data={'name': 'voice', 'channel_type': 'voice', 'user_limit': -1})
        self.assertFalse(f3.is_valid())
        self.assertIn('user_limit', f3.errors)

        # Valid channel
        f4 = ChannelForm(data={'name': '  gaming-chat  ', 'channel_type': 'text', 'cooldown': 10})
        self.assertTrue(f4.is_valid())
        self.assertEqual(f4.cleaned_data['name'], 'gaming-chat')

    def test_p1_category_form_validation(self):
        """Verify category validation rejects empty name and trims whitespace."""
        f1 = CategoryForm(data={'name': '  '})
        self.assertFalse(f1.is_valid())
        self.assertIn('name', f1.errors)

        f2 = CategoryForm(data={'name': '  Announcements  '})
        self.assertTrue(f2.is_valid())
        self.assertEqual(f2.cleaned_data['name'], 'Announcements')

    def test_p1_voice_channel_direct_visit(self):
        """Verify direct visit to voice channel URL resolves properly and renders voice controls."""
        url_voice = reverse('chat_channel', kwargs={'channel_slug': self.voice_channel.slug})
        resp = self.client_owner.get(url_voice)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn("Voice Lounge", content)
        self.assertIn("Connect to Voice", content)

    def test_channel_edit_persistence(self):
        """Verify channel edits persist after submission."""
        url_edit = reverse('edit_channel', kwargs={'channel_slug': self.channel.slug})
        resp = self.client_owner.post(url_edit, {
            'name': 'general-updated',
            'description': 'Updated topic description',
            'cooldown': 15,
        })
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.name, 'general-updated')
        self.assertEqual(self.channel.description, 'Updated topic description')
        self.assertEqual(self.channel.cooldown, 15)

    def test_profile_edit_display_name_and_email_validation(self):
        """Verify empty display name is rejected and email can be updated."""
        # Empty display name
        resp = self.client_owner.post(reverse('profile_edit'), {
            'display_name': '   ',
            'bio': 'Test bio'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Display name cannot be empty", resp.content.decode('utf-8'))

        # Valid display name
        resp_valid = self.client_owner.post(reverse('profile_edit'), {
            'display_name': 'Server Boss',
            'bio': 'New bio'
        })
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.first_name, 'Server Boss')

        # Account email update
        resp_email = self.client_owner.post(reverse('profile_edit'), {
            'account_update': '1',
            'email': 'owner@example.com'
        })
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, 'owner@example.com')

    def test_community_ban_by_user_id_and_rejoin_prevention(self):
        """Verify mod can ban by User ID even after user leaves, and user cannot rejoin."""
        # Member leaves server
        CommunityMember.objects.filter(community=self.community, user=self.member).delete()
        self.assertFalse(CommunityMember.objects.filter(community=self.community, user=self.member).exists())

        # Target has unique_id
        target_uid = self.member.profile.unique_id
        self.assertTrue(target_uid.startswith('CZ-'))

        # Owner bans member using User ID in community settings
        url_settings = f"/community/settings/?c={self.community.slug}&tab=bans"
        resp_ban = self.client_owner.post(url_settings, {
            'action': 'ban_member',
            'identifier': target_uid,
            'reason': 'Violated guidelines and left server'
        })
        self.assertEqual(resp_ban.status_code, 302)

        # Ban record exists
        ban = CommunityBan.objects.filter(community=self.community, user=self.member).first()
        self.assertIsNotNone(ban)
        self.assertEqual(ban.banned_by, self.owner)
        self.assertEqual(ban.reason, 'Violated guidelines and left server')

        # User tries to rejoin via invite code
        invite = CommunityInvite.objects.create(community=self.community, code='test-ban-code', max_uses=0, created_by=self.owner)
        resp_join = self.client_member.post(reverse('create_community'), {
            'action': 'join',
            'invite_code': 'test-ban-code'
        })
        self.assertEqual(resp_join.status_code, 200)
        self.assertIn("banned", resp_join.content.decode('utf-8').lower())
        self.assertFalse(CommunityMember.objects.filter(community=self.community, user=self.member).exists())

        # Unban user via User ID
        resp_unban = self.client_owner.post(url_settings, {
            'action': 'unban_member',
            'identifier': target_uid
        })
        self.assertEqual(resp_unban.status_code, 302)
        self.assertFalse(CommunityBan.objects.filter(community=self.community, user=self.member).exists())

        # Now user can rejoin successfully
        resp_join_success = self.client_member.post(reverse('create_community'), {
            'action': 'join',
            'invite_code': 'test-ban-code'
        })
        self.assertEqual(resp_join_success.status_code, 302)
        self.assertTrue(CommunityMember.objects.filter(community=self.community, user=self.member).exists())

    def test_moderation_apis_ban_unban_kick(self):
        """Verify moderation REST endpoints /ban/, /unban/, and /kick/ using User ID."""
        target_uid = self.member.profile.unique_id

        # Ban via API
        url_ban = f"/community/api/community/{self.community.slug}/ban/"
        resp = self.client_owner.post(url_ban, {
            'identifier': target_uid,
            'reason': 'API Ban Test'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertTrue(CommunityBan.objects.filter(community=self.community, user=self.member).exists())

        # Unban via API
        url_unban = f"/community/api/community/{self.community.slug}/unban/"
        resp_unban = self.client_owner.post(url_unban, {
            'identifier': target_uid
        })
        self.assertEqual(resp_unban.status_code, 200)
        data_unban = resp_unban.json()
        self.assertEqual(data_unban.get('status'), 'ok')
        self.assertFalse(CommunityBan.objects.filter(community=self.community, user=self.member).exists())

        # Re-add member and test kick via API
        CommunityMember.objects.create(community=self.community, user=self.member)
        url_kick = f"/community/api/community/{self.community.slug}/kick/"
        resp_kick = self.client_owner.post(url_kick, {
            'identifier': target_uid,
            'reason': 'API Kick Test'
        })
        self.assertEqual(resp_kick.status_code, 200)
        self.assertEqual(resp_kick.json().get('status'), 'ok')
        self.assertFalse(CommunityMember.objects.filter(community=self.community, user=self.member).exists())

    def test_display_name_and_nickname_hierarchy(self):
        """Verify display name and nickname precedence: Server Nickname > Profile Display Name > Username."""
        member_obj = CommunityMember.objects.get(community=self.community, user=self.member)

        # Baseline: Username fallback
        self.assertEqual(self.member.display_name, 'regular_member')
        self.assertEqual(member_obj.get_display_name(), 'regular_member')

        # Profile Display Name set
        profile = self.member.profile
        profile.display_name = 'Chill Knight'
        profile.save()
        self.assertEqual(self.member.display_name, 'Chill Knight')
        member_obj = CommunityMember.objects.select_related('user', 'user__profile').get(id=member_obj.id)
        self.assertEqual(member_obj.get_display_name(), 'Chill Knight')

        # Server Nickname set
        member_obj.nickname = 'Server Lord'
        member_obj.save()
        self.assertEqual(member_obj.get_display_name(), 'Server Lord')
        # Global display name remains unaffected by server nickname
        self.assertEqual(self.member.display_name, 'Chill Knight')

        # Reset server nickname
        member_obj.nickname = ''
        member_obj.save()
        self.assertEqual(member_obj.get_display_name(), 'Chill Knight')

    def test_change_nickname_permissions(self):
        """Verify CHANGE_NICKNAME and MANAGE_NICKNAMES role permissions for change_nickname API."""
        member_obj = CommunityMember.objects.get(community=self.community, user=self.member)
        url = f"/community/api/community/{self.community.slug}/nickname/"

        # 1. Member without CHANGE_NICKNAME permission -> 403
        resp = self.client_member.post(url, {'nickname': 'SneakyNick'})
        self.assertEqual(resp.status_code, 403)

        # 2. Grant CHANGE_NICKNAME via role
        nick_role = Role.objects.create(
            community=self.community,
            name='NickChanger',
            CHANGE_NICKNAME=True
        )
        member_obj.roles.add(nick_role)

        resp = self.client_member.post(url, {'nickname': 'AllowedNick'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data.get('nickname'), 'AllowedNick')
        member_obj.refresh_from_db()
        self.assertEqual(member_obj.nickname, 'AllowedNick')

        # 3. Regular member cannot change owner's nickname -> 403
        resp = self.client_member.post(url, {'nickname': 'HackedOwner', 'target_username': self.owner.username})
        self.assertEqual(resp.status_code, 403)

        # 4. Grant MANAGE_NICKNAMES via role
        manage_role = Role.objects.create(
            community=self.community,
            name='NickManager',
            MANAGE_NICKNAMES=True
        )
        member_obj.roles.add(manage_role)

        resp = self.client_member.post(url, {'nickname': 'ModdedOwner', 'target_username': self.owner.username})
        self.assertEqual(resp.status_code, 200)

        # 5. Reset nickname via API keyword 'reset'
        resp = self.client_member.post(url, {'nickname': 'reset'})
        self.assertEqual(resp.status_code, 200)
        member_obj.refresh_from_db()
        self.assertEqual(member_obj.nickname, '')


class PermissionBoundaryRegressionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='privacy_owner', password='password123')
        self.member = User.objects.create_user(username='privacy_member', password='password123')
        self.stranger = User.objects.create_user(username='privacy_stranger', password='password123')
        self.community = Community.objects.create(name='Private Hub', slug='private-hub', owner=self.owner)
        self.category = ChannelCategory.objects.create(name='Private Category', community=self.community)
        self.channel = Channel.objects.create(
            name='staff-room', slug='staff-room', category=self.category,
            channel_type='text', is_private=True,
        )
        self.everyone = Role.objects.create(
            community=self.community, name='@everyone', VIEW_CHANNEL=True,
            SEND_MESSAGES=True, EMBED_LINKS=True, ATTACH_FILES=True,
        )
        self.member_record = CommunityMember.objects.create(
            community=self.community, user=self.member,
        )

    def test_everyone_cannot_grant_administrator_even_if_malformed(self):
        self.everyone.ADMINISTRATOR = True
        self.everyone.save(update_fields=['ADMINISTRATOR'])
        duplicate_default = Role.objects.create(
            community=self.community, name='@Everyone', ADMINISTRATOR=True,
        )
        self.member_record.roles.add(duplicate_default)

        self.assertFalse(self.member_record.has_permission('ADMINISTRATOR'))
        self.everyone.refresh_from_db()
        self.assertFalse(self.everyone.ADMINISTRATOR)

    def test_private_channel_requires_explicit_view_override(self):
        self.assertFalse(can_user_view_channel(self.member, self.channel))

        client = Client()
        client.force_login(self.member)
        response = client.get(reverse('chat_channel', kwargs={'channel_slug': self.channel.slug}))
        self.assertEqual(response.status_code, 403)

        ChannelPermission.objects.create(
            channel=self.channel, role=self.everyone, view_channel=True,
        )
        self.assertTrue(can_user_view_channel(self.member, self.channel))

        response = client.get(reverse('chat_channel', kwargs={'channel_slug': self.channel.slug}))
        self.assertEqual(response.status_code, 200)

    def test_channel_action_override_denies_community_permission(self):
        ChannelPermission.objects.create(
            channel=self.channel, role=self.everyone,
            view_channel=True, send_messages=False,
        )
        self.assertFalse(can_user_perform_channel_action(
            self.member, self.channel, 'send_messages', 'SEND_MESSAGES'
        ))

    def test_message_search_excludes_private_channels_without_access(self):
        Message.objects.create(channel=self.channel, author=self.owner, content='private-note')
        client = Client()
        client.force_login(self.member)
        url = reverse('search_messages') + f'?c={self.community.slug}&q=private-note'
        self.assertEqual(client.get(url).json()['count'], 0)

    def test_member_specific_deny_overrides_role_allow(self):
        ChannelPermission.objects.create(
            channel=self.channel, role=self.everyone, view_channel=True,
        )
        ChannelPermission.objects.create(
            channel=self.channel, user=self.member, view_channel=False,
        )
        self.assertFalse(can_user_view_channel(self.member, self.channel))

    def test_dm_session_requires_participant_and_honors_recipient_controls(self):
        session = DirectMessageSession.objects.create(user1=self.owner, user2=self.member)
        self.assertEqual(get_dm_session_for_user(session.id, self.member), session)
        self.assertIsNone(get_dm_session_for_user(session.id, self.stranger))
        self.assertTrue(can_send_dm(session, self.owner))

        self.member.profile.dm_setting = 'friends'
        self.member.profile.save(update_fields=['dm_setting'])
        self.assertFalse(can_send_dm(session, self.owner))
        Friendship.objects.create(user1=self.owner, user2=self.member)
        self.assertTrue(can_send_dm(session, self.owner))

        Block.objects.create(blocker=self.member, blocked=self.owner)
        self.assertFalse(can_send_dm(session, self.owner))

    def test_embed_urls_only_allow_http_schemes(self):
        self.assertIsNone(ChatService.clean_embed_data({
            'type': 'gif', 'url': 'javascript:alert(1)',
        }))
        self.assertEqual(ChatService.clean_embed_data({
            'type': 'gif', 'url': 'https://cdn.example.test/clip.gif',
        }), {'type': 'gif', 'url': 'https://cdn.example.test/clip.gif'})
