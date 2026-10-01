from django.core.management.base import BaseCommand

from apps.printing.services import sync_print_jobs


class Command(BaseCommand):
    help = "Poll Epson Connect for print job status updates and sync order statuses."

    def handle(self, *args, **options):
        sync_print_jobs()
        self.stdout.write(self.style.SUCCESS("Print job statuses synced."))
