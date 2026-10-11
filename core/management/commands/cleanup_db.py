from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chat.models import Message
from accounts.models import Report

class Command(BaseCommand):
    help = 'Cleans up old deleted messages and resolved reports from the database'

    def handle(self, *args, **kwargs):
        # 1. Delete messages that were softly deleted more than 1 day ago
        one_day_ago = timezone.now() - timedelta(days=1)
        deleted_messages = Message.objects.filter(deleted_at__lte=one_day_ago)
        msgs_count = deleted_messages.count()
        deleted_messages.delete()
        
        # 2. Delete resolved reports older than 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        resolved_reports = Report.objects.filter(is_resolved=True, created_at__lte=seven_days_ago)
        reports_count = resolved_reports.count()
        resolved_reports.delete()
        
        # 3. Aggressive storage saving: Delete ALL messages older than 60 days to prevent infinite growth
        sixty_days_ago = timezone.now() - timedelta(days=60)
        old_messages = Message.objects.filter(created_at__lte=sixty_days_ago)
        old_msgs_count = old_messages.count()
        old_messages.delete()
        
        total_msgs = msgs_count + old_msgs_count
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {total_msgs} old messages and {reports_count} old reports.'))
