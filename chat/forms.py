from django import forms
from .models import Channel, ChannelCategory

class ChannelForm(forms.ModelForm):
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'What is this channel about?', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit; resize: vertical;'})
    )
    cooldown = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0', 'min': '0', 'max': '21600', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'})
    )
    user_limit = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0 (Unlimited)', 'min': '0', 'max': '99', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'})
    )

    class Meta:
        model = Channel
        fields = ['name', 'description', 'channel_type', 'cooldown', 'user_limit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'new-channel', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
            'channel_type': forms.Select(choices=Channel.CHANNEL_TYPES, attrs={'class': 'form-control', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("Channel name cannot be blank.")
        if len(name) < 2:
            raise forms.ValidationError("Channel name must be at least 2 characters long.")
        if len(name) > 50:
            raise forms.ValidationError("Channel name cannot exceed 50 characters.")
        return name

    def clean_cooldown(self):
        val = self.cleaned_data.get('cooldown')
        if val is None:
            return 0
        if val < 0:
            raise forms.ValidationError("Cooldown cannot be negative.")
        if val > 21600:
            raise forms.ValidationError("Cooldown cannot exceed 6 hours (21600 seconds).")
        return val

    def clean_user_limit(self):
        val = self.cleaned_data.get('user_limit')
        if val is None:
            return 0
        if val < 0:
            raise forms.ValidationError("User limit cannot be negative.")
        if val > 99:
            raise forms.ValidationError("User limit cannot exceed 99 users.")
        return val

class CategoryForm(forms.ModelForm):
    class Meta:
        model = ChannelCategory
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CATEGORY NAME', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("Category name cannot be blank.")
        if len(name) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters long.")
        if len(name) > 50:
            raise forms.ValidationError("Category name cannot exceed 50 characters.")
        return name
