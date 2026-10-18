from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.utils import timezone
from profiles.models import Profile
from captcha.models import CaptchaStore

class UniqueIDAndRecoveryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testhero',
            email='hero@example.com',
            password='InitialPassword123!'
        )
        # Profile is created via post_save signal
        self.profile = self.user.profile
        cache.clear()

    def test_unique_id_and_recovery_key_generated(self):
        """Verifies Unique ID and Recovery Key are created upon user registration."""
        self.assertIsNotNone(self.profile.unique_id)
        self.assertTrue(self.profile.unique_id.startswith('CZ-'))
        self.assertIsNotNone(self.profile.recovery_key)
        self.assertTrue(self.profile.recovery_key.startswith('CZ-REC-'))

    def test_multi_identifier_authentication(self):
        """Verifies user can authenticate using username, email, or Unique ID."""
        # 1. By username
        auth_user = authenticate(username='testhero', password='InitialPassword123!')
        self.assertEqual(auth_user, self.user)

        # 2. By email
        auth_email = authenticate(username='hero@example.com', password='InitialPassword123!')
        self.assertEqual(auth_email, self.user)

        # 3. By Unique ID (with CZ- prefix)
        auth_uid = authenticate(username=self.profile.unique_id, password='InitialPassword123!')
        self.assertEqual(auth_uid, self.user)

        # 4. By Unique ID (lowercase or without CZ-)
        raw_num = self.profile.unique_id.replace('CZ-', '')
        auth_num = authenticate(username=raw_num, password='InitialPassword123!')
        self.assertEqual(auth_num, self.user)

    def test_zero_cost_account_recovery_and_global_logout(self):
        """
        Verifies account recovery with recovery key resets password,
        rotates recovery key, and purges all active sessions across devices.
        """
        client = Client()
        client.login(username='testhero', password='InitialPassword123!')
        
        # Verify active session exists in DB
        user_id_str = str(self.user.id)
        active_sessions = [
            s for s in Session.objects.filter(expire_date__gte=timezone.now())
            if s.get_decoded().get('_auth_user_id') == user_id_str
        ]
        self.assertGreater(len(active_sessions), 0)

        old_recovery_key = self.profile.recovery_key
        
        # Perform recovery
        response = self.client.post('/accounts/recover/', {
            'identifier': self.profile.unique_id,
            'recovery_secret': old_recovery_key,
            'new_password': 'BrandNewPassword999!',
            'confirm_password': 'BrandNewPassword999!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('success_data', response.context)

        # Verify old password fails
        self.assertIsNone(authenticate(username='testhero', password='InitialPassword123!'))

        # Verify new password succeeds with username and Unique ID
        self.assertIsNotNone(authenticate(username='testhero', password='BrandNewPassword999!'))
        self.assertIsNotNone(authenticate(username=self.profile.unique_id, password='BrandNewPassword999!'))

        # Verify all previous sessions were purged globally
        remaining_sessions = [
            s for s in Session.objects.filter(expire_date__gte=timezone.now())
            if s.get_decoded().get('_auth_user_id') == user_id_str
        ]
        self.assertEqual(len(remaining_sessions), 0)

        # Verify recovery key was rotated
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.recovery_key, old_recovery_key)

    def test_admin_emergency_pin_recovery(self):
        """Verifies that an Admin-issued Emergency PIN allows password reset."""
        # Issue emergency PIN
        self.profile.emergency_pin = "998877"
        self.profile.emergency_pin_expires_at = timezone.now() + timezone.timedelta(hours=1)
        self.profile.save()

        response = self.client.post('/accounts/recover/', {
            'identifier': 'hero@example.com',
            'recovery_secret': '998877',
            'new_password': 'EmergencyNewPass123!',
            'confirm_password': 'EmergencyNewPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('success_data', response.context)

        # Emergency PIN is cleared after use
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.emergency_pin, "")

        # New password works
        self.assertIsNotNone(authenticate(username='testhero', password='EmergencyNewPass123!'))

    def test_recovery_locks_after_five_invalid_secrets(self):
        cache.clear()
        old_password = 'InitialPassword123!'
        for _ in range(5):
            self.client.post('/accounts/recover/', {
                'identifier': self.profile.unique_id,
                'recovery_secret': 'WRONG-SECRET',
                'new_password': 'AttemptedPassword123!',
                'confirm_password': 'AttemptedPassword123!',
            })

        response = self.client.post('/accounts/recover/', {
            'identifier': self.profile.unique_id,
            'recovery_secret': self.profile.recovery_key,
            'new_password': 'AttemptedPassword123!',
            'confirm_password': 'AttemptedPassword123!',
        })
        self.assertContains(response, 'Too many recovery attempts', status_code=200)
        self.assertIsNotNone(authenticate(username='testhero', password=old_password))

    def test_user_registration_success_and_login(self):
        """Verifies new user registration logs in user without 500 or multi-backend error."""
        captcha = CaptchaStore.objects.create(challenge='ABCD', response='ABCD')
        response = self.client.post('/register/', {
            'username': 'newuser123',
            'email': 'newuser123@example.com',
            'password1': 'StrongP@ssw0rd99!',
            'password2': 'StrongP@ssw0rd99!',
            'captcha_0': captcha.hashkey,
            'captcha_1': 'abcd',
            'tos_agreed': True,
            'join_official': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser123').exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newuser123').id)

