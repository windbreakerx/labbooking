import csv
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.academics.models import Semester
from apps.scheduling.models import LabSession, LabSessionStatus, ScheduleEntry, WeekParity


class Command(BaseCommand):
    help = "Генерация LabSession из ScheduleEntry на N недель вперёд"

    def add_arguments(self, parser):
        parser.add_argument("--weeks", type=int, default=4)

    def handle(self, *args, **options):
        weeks = options["weeks"]
        semester = Semester.objects.filter(is_active=True).first()
        if not semester:
            self.stderr.write("Нет активного семестра.")
            return

        today = timezone.now().date()
        created = 0
        for entry in ScheduleEntry.objects.filter(is_active=True, semester=semester):
            for week_offset in range(weeks):
                day = today + timedelta(weeks=week_offset)
                day += timedelta(days=(entry.weekday - day.weekday()) % 7)
                if entry.week_parity != WeekParity.BOTH:
                    iso_week = day.isocalendar()[1]
                    is_even = iso_week % 2 == 0
                    if entry.week_parity == WeekParity.EVEN and not is_even:
                        continue
                    if entry.week_parity == WeekParity.ODD and is_even:
                        continue

                starts = timezone.make_aware(
                    datetime.combine(day, entry.start_time),
                    timezone.get_current_timezone(),
                )
                ends = starts + timedelta(minutes=entry.duration_minutes)
                if LabSession.objects.filter(
                    lab_work=entry.lab_work,
                    room=entry.room,
                    starts_at=starts,
                ).exists():
                    continue
                LabSession.objects.create(
                    lab_work=entry.lab_work,
                    room=entry.room,
                    semester=semester,
                    teacher=entry.teacher,
                    starts_at=starts,
                    ends_at=ends,
                    capacity=entry.capacity,
                    status=LabSessionStatus.OPEN,
                )
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Создано слотов: {created}"))
