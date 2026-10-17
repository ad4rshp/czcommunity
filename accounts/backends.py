from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrUsernameOrUIDBackend(ModelBackend):
    """
    Allows authentication using:
    1. Username
    2. Email address (case-insensitive)
    3. ChillZone Unique ID (e.g. 'CZ-858666' or '858666')
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        identifier = str(username).strip()

        # 1. Try username or email (case-insensitive)
        user = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()

        # 2. If not found, check unique_id on Profile
        if not user:
            uid_candidate = identifier.upper()
            if not uid_candidate.startswith("CZ-") and uid_candidate.isalnum():
                uid_alt = f"CZ-{uid_candidate}"
            else:
                uid_alt = uid_candidate

            user = User.objects.filter(
                Q(profile__unique_id__iexact=uid_candidate) |
                Q(profile__unique_id__iexact=uid_alt)
            ).first()

        if user and user.check_password(password):
            return user

        return None
