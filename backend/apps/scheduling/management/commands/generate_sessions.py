from django.core.management.base import BaseCommand

from apps.academics.models import Semester
from apps.scheduling.services.slot_generation import generate_lab_sessions


class Command(BaseCommand):
    help = (
        "Создать слоты LabSession для каждой ЛР с default_room: "
        "все будние дни и все пары в пределах горизонта записи."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            type=int,
            default=2,
            help="Минимальный горизонт в неделях (плюс BOOKING_HORIZON_DAYS)",
        )

    def handle(self, *args, **options):
        semester = Semester.objects.filter(is_active=True).first()
        if not semester:
            self.stderr.write(self.style.ERROR("Нет активного семестра."))
            return

        created = generate_lab_sessions(semester=semester, weeks=options["weeks"])
        self.stdout.write(self.style.SUCCESS(f"Создано новых слотов: {created}"))
