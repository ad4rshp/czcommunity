from django import forms
from .models import Channel, ChannelCategory

class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ['name', 'description', 'channel_type', 'cooldown', 'user_limit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'new-channel', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'What is this channel about?', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit; resize: vertical;'}),
            'channel_type': forms.Select(choices=Channel.CHANNEL_TYPES, attrs={'class': 'form-control', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
            'cooldown': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0', 'min': '0', 'max': '21600', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
            'user_limit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0 (Unlimited)', 'min': '0', 'max': '99', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
        }

class CategoryForm(forms.ModelForm):
    class Meta:
        model = ChannelCategory
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CATEGORY NAME', 'style': 'width: 100%; padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-primary); box-sizing: border-box; margin-top: 5px; font-family: inherit;'}),
        }
