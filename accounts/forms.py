from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.safestring import mark_safe

from captcha.fields import CaptchaField

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Required. Inform a valid email address.')
    captcha = CaptchaField()
    tos_agreed = forms.BooleanField(
        required=True,
        label=mark_safe('I agree to the <a href="/tos/" target="_blank" style="color: var(--accent); text-decoration: none;">Terms of Service</a> and <a href="/privacy/" target="_blank" style="color: var(--accent); text-decoration: none;">Privacy Policy</a>'),
        error_messages={'required': 'You must agree to the Terms of Service to create an account.'}
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email address already exists.')
        return email
