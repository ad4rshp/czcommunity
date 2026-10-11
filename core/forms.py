from django import forms
from .models import DashboardConfig

class DashboardConfigForm(forms.ModelForm):
    class Meta:
        model = DashboardConfig
        fields = [
            'welcome_message',
            'show_announcement', 'announcement_title', 'announcement_content',
            'show_rules', 'rules_text',
            'show_quick_actions'
        ]
        widgets = {
            'announcement_content': forms.Textarea(attrs={'rows': 4}),
            'rules_text': forms.Textarea(attrs={'rows': 4}),
        }
