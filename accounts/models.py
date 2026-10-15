from django.db import models
from django.contrib.auth.models import User

class Block(models.Model):
    blocker = models.ForeignKey(User, related_name='blocking', on_delete=models.CASCADE)
    blocked = models.ForeignKey(User, related_name='blocked_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        verbose_name = 'Blocked User'
        verbose_name_plural = 'Blocked Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"

class Report(models.Model):
    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('inappropriate', 'Inappropriate Content'),
        ('hate_speech', 'Hate Speech'),
        ('other', 'Other'),
    ]
    
    reporter = models.ForeignKey(User, related_name='reports_filed', on_delete=models.CASCADE)
    reported_user = models.ForeignKey(User, related_name='reports_received', on_delete=models.CASCADE)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'User Report'
        verbose_name_plural = 'User Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report by {self.reporter.username} against {self.reported_user.username}"
