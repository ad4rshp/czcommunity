from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from chat.models import Community, CommunityMember, Role, CommunityInvite, AuditLog

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
