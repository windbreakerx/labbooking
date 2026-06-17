from django.core.management.base import BaseCommand

from apps.bookings.services import BookingService


class Command(BaseCommand):
    help = "Авто-проставление VISITED для завершённых слотов"

    def handle(self, *args, **options):
        count = BookingService().mark_visited_for_ended_sessions()
        self.stdout.write(self.style.SUCCESS(f"Обновлено записей: {count}"))
