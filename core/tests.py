from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from chat.models import Community, CommunityMember, Role, CommunityInvite, AuditLog
from core.middleware import RateLimitMiddleware

class CoreRoleAndPermissionsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='server_owner', password='password123')
        self.mod = User.objects.create_user(username='moderator_user', password='password123')
        self.regular = User.objects.create_user(username='ordinary_member', password='password123')

        self.community = Community.objects.create(name='Security Citadel', slug='security-citadel', owner=self.owner)
        
        # Member records
        self.owner_member = CommunityMember.objects.create(community=self.community, user=self.owner)
        self.mod_member = CommunityMember.objects.create(community=self.community, user=self.mod)
        self.reg_member = CommunityMember.objects.create(community=self.community, user=self.regular)

        # Moderator role with MANAGE_ROLES
        self.mod_role = Role.objects.create(
            community=self.community, 
            name='Moderator', 
            color='#3498DB', 
            position=10,
            MANAGE_ROLES=True
        )
        self.mod_member.roles.add(self.mod_role)

        self.client_owner = Client()
        self.client_owner.login(username='server_owner', password='password123')

        self.client_mod = Client()
        self.client_mod.login(username='moderator_user', password='password123')

        self.client_reg = Client()
        self.client_reg.login(username='ordinary_member', password='password123')

    def test_rate_limiter_uses_address_appended_by_reverse_proxy(self):
        request = RequestFactory().post(
            '/accounts/recover/',
            HTTP_X_FORWARDED_FOR='198.51.100.44, 203.0.113.18',
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(
            RateLimitMiddleware(None).get_client_ip(request),
            '203.0.113.18',
        )

    def test_create_community_validation(self):
        """Verify server creation validates non-empty name and trims whitespace."""
        url = reverse('create_community')
        
        # Blank name
        resp_blank = self.client_owner.post(url, {'action': 'create', 'name': '   ', 'description': 'Empty server'})
        self.assertEqual(resp_blank.status_code, 200)
        self.assertIn("Server name cannot be blank", resp_blank.content.decode('utf-8'))

        # Valid name
        resp_valid = self.client_owner.post(url, {'action': 'create', 'name': '  Awesome Community  ', 'description': 'Cool server'})
        self.assertEqual(resp_valid.status_code, 302)
        comm = Community.objects.filter(name='Awesome Community').first()
        self.assertIsNotNone(comm)
        self.assertTrue(AuditLog.objects.filter(community=comm, action='Created community server').exists())

    def test_role_creation_and_restriction(self):
        """Verify role creation works for owner and moderator, but is rejected for ordinary member."""
        url = f"{reverse('community_settings')}?c={self.community.slug}&tab=roles"

        # Ordinary member attempt to create role
        resp_reg = self.client_reg.post(url, {
            'action': 'create_role',
            'name': 'Hacker Role',
            'color': '#FF0000'
        })
        self.assertFalse(Role.objects.filter(community=self.community, name='Hacker Role').exists())

        # Moderator with MANAGE_ROLES creates role
        resp_mod = self.client_mod.post(url, {
            'action': 'create_role',
            'name': 'VIP Member',
            'color': '#E91E63'
        })
        self.assertTrue(Role.objects.filter(community=self.community, name='VIP Member').exists())
        self.assertTrue(AuditLog.objects.filter(community=self.community, action='Created role: VIP Member').exists())

    def test_role_hierarchy_and_everyone_administrator_are_enforced(self):
        url = f"{reverse('community_settings')}?c={self.community.slug}&tab=roles"
        higher_role = Role.objects.create(
            community=self.community,
            name='Server Lead',
            position=20,
            SEND_MESSAGES=True,
        )

        self.client_mod.post(url, {
            'action': 'update_role',
            'role_id': higher_role.id,
            'name': 'Escalated Role',
            'SEND_MESSAGES': 'on',
        })
        higher_role.refresh_from_db()
        self.assertEqual(higher_role.name, 'Server Lead')
        self.assertTrue(higher_role.SEND_MESSAGES)

        everyone = Role.objects.get(community=self.community, name='@everyone')
        self.client_owner.post(url, {
            'action': 'update_role',
            'role_id': everyone.id,
            'ADMINISTRATOR': 'on',
        })
        everyone.refresh_from_db()
        self.assertFalse(everyone.ADMINISTRATOR)

    def test_invite_creation_validation_and_permission(self):
        """Verify negative invite limits are rejected, ordinary member is blocked, moderator can create invite."""
        url = f"{reverse('community_settings')}?c={self.community.slug}&tab=invites"

        # Negative max uses rejected
        resp_neg = self.client_owner.post(url, {
            'action': 'create_invite',
            'max_uses': '-5',
            'expires_in': '86400'
        })
        self.assertFalse(CommunityInvite.objects.filter(community=self.community, max_uses__lt=0).exists())

        # Ordinary member cannot create invite via settings
        resp_reg = self.client_reg.post(url, {
            'action': 'create_invite',
            'max_uses': '10',
            'expires_in': '86400'
        })
        self.assertFalse(CommunityInvite.objects.filter(community=self.community, created_by=self.regular).exists())

        # Moderator can create invite
        resp_mod = self.client_mod.post(url, {
            'action': 'create_invite',
            'max_uses': '5',
            'expires_in': '86400'
        })
        invite = CommunityInvite.objects.filter(community=self.community, created_by=self.mod).first()
        self.assertIsNotNone(invite)
        self.assertEqual(invite.max_uses, 5)
        self.assertTrue(AuditLog.objects.filter(community=self.community, user=self.mod).exists())

    def test_friends_view_and_member_directory_reverse(self):
        """Verify /friends/ loads and member_directory reverse URL is found without NoReverseMatch."""
        from django.urls import reverse
        # Check reverse resolution
        url_dir = reverse('member_directory')
        self.assertTrue(url_dir.startswith('/profiles/'))
        
        # Check /friends/ renders without template reverse errors
        resp = self.client_owner.get(reverse('friends'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ALL FRIENDS", resp.content.decode('utf-8'))

    def test_create_and_join_community_messages_no_name_error(self):
        """Verify join and create actions do not crash with NameError for messages."""
        # Create invite
        invite = CommunityInvite.objects.create(
            community=self.community,
            code='testjoin123',
            created_by=self.owner,
            max_uses=10
        )
        
        # Regular user joins via invite code
        resp_join = self.client_reg.post(reverse('create_community'), {
            'action': 'join',
            'invite_code': 'testjoin123'
        })
        self.assertEqual(resp_join.status_code, 302)
        
        # User joins official server
        resp_official = self.client_reg.post(reverse('create_community'), {
            'action': 'join_official'
        })
        self.assertEqual(resp_official.status_code, 302)

    def test_delete_community_messages_no_name_error(self):
        """Verify community deletion works without NameError for messages."""
        temp_comm = Community.objects.create(name='Temp Comm', slug='temp-comm', owner=self.owner)
        resp = self.client_owner.post(f"{reverse('delete_community')}?c={temp_comm.slug}", {
            'action': 'delete_community_confirm',
            'community_slug': temp_comm.slug
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Community.objects.filter(slug='temp-comm').exists())

    def test_category_urls_graceful_handling_no_raw_404(self):
        """Verify non-existent category IDs/slugs redirect safely rather than crashing with unhandled 404."""
        # Non-existent ID in manage category
        resp_manage = self.client_owner.get('/community/chat/category/999999/manage/')
        self.assertEqual(resp_manage.status_code, 302)
        self.assertEqual(resp_manage.url, reverse('chat'))

        # Non-existent slug in manage category
        resp_slug = self.client_owner.get('/community/chat/category/non-existent-category/manage/')
        self.assertEqual(resp_slug.status_code, 302)
        self.assertEqual(resp_slug.url, reverse('chat'))

        # Non-existent ID in add channel
        resp_add = self.client_owner.get('/community/chat/category/999999/add-channel/')
        self.assertEqual(resp_add.status_code, 302)
        self.assertEqual(resp_add.url, reverse('chat'))
