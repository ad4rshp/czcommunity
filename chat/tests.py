from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from chat.models import Community, ChannelCategory, Channel, CommunityMember, Role, CommunityInvite
from chat.forms import ChannelForm, CategoryForm

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
