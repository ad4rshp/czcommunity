from django.db import models

class DashboardConfig(models.Model):
    announcement_title = models.CharField(max_length=200, default="Welcome to CHILL ZONE")
    announcement_content = models.TextField(default="We're building a place for our community to hang out, play and connect. Check out the community chat to join the conversation.")
    show_announcement = models.BooleanField(default=True)
    show_rules = models.BooleanField(default=True)
    rules_text = models.TextField(blank=True, default="1. Be respectful to others.\n2. No spamming or self-promotion.\n3. Keep conversations civil.")
    show_quick_actions = models.BooleanField(default=True)
    welcome_message = models.TextField(blank=True, default="Welcome to the Chill Zone Admin Dashboard!")

    # New global settings
    is_maintenance_mode = models.BooleanField(default=False, help_text="Turn on to put the site in maintenance mode.")
    show_beta_warning = models.BooleanField(default=True, help_text="Show the BETA warning card on the landing page.")
    maintenance_message = models.TextField(default="We are currently undergoing maintenance. Please check back later.")
    
    class Meta:
        verbose_name = "Site Setting & Dashboard Config"
        verbose_name_plural = "Site Settings & Dashboard Config"

    def __str__(self):
        return "Global Site Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(DashboardConfig, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
