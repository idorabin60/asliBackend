import os
import django
from django_cron import CronJobBase, Schedule
from django.core.management import call_command

# Ensure Django settings are loaded

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "asliBackend.asliBackend.settings")
django.setup()


class CreateHomeworkCronJob(CronJobBase):
    """Runs the `create_homework` management command every hour."""

    RUN_EVERY_MINS = 60  # Runs every 60 minutes
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'homeWork.create_homework_cron'  # Unique identifier

    def do(self):
        print("🔄 Running CreateHomeworkCronJob...")
        try:
            call_command("create_homework")  # Call the create_homework command
            print("✅ CreateHomeworkCronJob completed successfully.")
        except Exception as e:
            print(f"❌ ERROR in CreateHomeworkCronJob: {e}")
