from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from profiles.models import Profile, Friendship, FriendRequest

class ProfilesAndSocialTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='user_alpha', password='password123')
        self.user_b = User.objects.create_user(username='user_beta', password='password123')
        
        self.client_a = Client()
        self.client_a.login(username='user_alpha', password='password123')
        
        self.client_b = Client()
        self.client_b.login(username='user_beta', password='password123')

    def test_send_friend_request_by_unique_id(self):
        """Verify users can send friend requests using their permanent Unique ID (e.g. CZ-XXXXXX)."""
        uid_b = self.user_b.profile.unique_id
        self.assertTrue(uid_b.startswith('CZ-'))

        url = reverse('send_friend_request_by_username')
        resp = self.client_a.post(url, {'username': uid_b})
        self.assertEqual(resp.status_code, 302)

        # Check friend request was created
        req = FriendRequest.objects.filter(sender=self.user_a, receiver=self.user_b).first()
        self.assertIsNotNone(req)

        # Cross request from B to A via A's unique ID auto-accepts friendship
        uid_a = self.user_a.profile.unique_id
        resp_b = self.client_b.post(url, {'username': uid_a})
        self.assertEqual(resp_b.status_code, 302)

        # Pending request should be resolved and friendship created
        self.assertFalse(FriendRequest.objects.filter(sender=self.user_a, receiver=self.user_b).exists())
        self.assertTrue(Friendship.objects.filter(user1=self.user_a, user2=self.user_b).exists() or
                        Friendship.objects.filter(user1=self.user_b, user2=self.user_a).exists())

    def test_get_user_id_api(self):
        """Verify REST API resolves username to permanent Unique ID."""
        url = reverse('get_user_id_api')
        resp = self.client_a.get(f"{url}?username={self.user_b.username}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('username'), self.user_b.username)
        self.assertEqual(data.get('unique_id'), self.user_b.profile.unique_id)

    def test_pending_tab_includes_incoming_and_outgoing_requests(self):
        FriendRequest.objects.create(sender=self.user_b, receiver=self.user_a)
        FriendRequest.objects.create(sender=self.user_a, receiver=self.user_b)

        response = self.client_a.get(reverse('friends'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('INCOMING', content)
        self.assertIn('OUTGOING', content)
        self.assertIn('PENDING REQUESTS', content)

    def test_check_username_api(self):
        """Test real-time username availability check API."""
        url = reverse('check_username_api')
        
        # Current user's own username should be reported as available / current
        resp = self.client_a.get(f"{url}?username={self.user_a.username}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('available'))
        self.assertTrue(resp.json().get('is_current'))

        # Another user's username should be unavailable
        resp = self.client_a.get(f"{url}?username={self.user_b.username}")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json().get('available'))

        # Reserved system username should be unavailable
        resp = self.client_a.get(f"{url}?username=admin")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json().get('available'))

        # Invalid username formats
        resp = self.client_a.get(f"{url}?username=ab")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json().get('available'))

        # Fresh available username
        resp = self.client_a.get(f"{url}?username=chill_hero99")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('available'))

    def test_change_username_success_and_conflict(self):
        """Test updating username via profile_edit."""
        edit_url = reverse('profile_edit')

        # 1. Successful change to available username
        resp = self.client_a.post(edit_url, {
            'account_update': '1',
            'username': 'alpha_renamed',
            'email': 'alpha@example.com',
            'display_name': 'Alpha New'
        })
        self.assertEqual(resp.status_code, 302)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.username, 'alpha_renamed')

        # 2. Attempt to take user_b's username should fail
        resp_conflict = self.client_a.post(edit_url, {
            'account_update': '1',
            'username': self.user_b.username,
            'email': 'alpha@example.com',
            'display_name': 'Alpha New'
        })
        self.user_a.refresh_from_db()
        # Should remain alpha_renamed
        self.assertEqual(self.user_a.username, 'alpha_renamed')
