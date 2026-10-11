import os
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # We only want to start the scheduler once.
        # Avoid running in management commands like migrate, shell, etc.
        if os.environ.get('RUN_MAIN', None) != 'true':
            return
            
        from apscheduler.schedulers.background import BackgroundScheduler
        from django_apscheduler.jobstores import DjangoJobStore
        from django.core.management import call_command

        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")

        def clean_db_job():
            print("Running scheduled DB cleanup...")
            call_command('cleanup_db')

        # Run the cleanup command every day at midnight
        scheduler.add_job(
            clean_db_job,
            trigger='cron',
            hour=0,
            minute=0,
            id='daily_cleanup',
            replace_existing=True
        )

        try:
            scheduler.start()
            print("APScheduler started successfully!")
        except Exception as e:
            print("Failed to start scheduler:", e)
