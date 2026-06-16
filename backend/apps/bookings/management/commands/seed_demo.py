from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.academics.models import Discipline, LabWork, Semester
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus, Room, TrainingCenter
from apps.users.models import User, UserRole


class Command(BaseCommand):
    help = "Загрузка демонстрационных данных для разработки"

    def handle(self, *args, **options):
        semester, _ = Semester.objects.get_or_create(
            name="2025–2026, весна",
            defaults={
                "start_date": timezone.now().date(),
                "end_date": timezone.now().date().replace(month=6, day=30),
                "is_active": True,
            },
        )

        discipline, _ = Discipline.objects.get_or_create(
            title="Физика",
            defaults={"code": "PHY-101", "semester": semester, "is_published": True},
        )

        lab_work, _ = LabWork.objects.get_or_create(
            discipline=discipline,
            number=1,
            defaults={
                "title": "Изучение закона Ома",
                "duration_minutes": 90,
                "is_published": True,
            },
        )

        tc, _ = TrainingCenter.objects.get_or_create(number=1, defaults={"name": "Главный корпус"})
        room, _ = Room.objects.get_or_create(
            training_center=tc,
            number="201",
            defaults={"capacity": 20},
        )

        staff, created = User.objects.get_or_create(
            email="staff@spmi.ru",
            defaults={
                "first_name": "Иван",
                "last_name": "Завлабов",
                "role": UserRole.LAB_ADMIN,
                "is_staff": True,
            },
        )
        if created:
            staff.set_password("staff123")
            staff.save()

        student, created = User.objects.get_or_create(
            email="student@stud.spmi.ru",
            defaults={
                "first_name": "Пётр",
                "last_name": "Студентов",
                "role": UserRole.STUDENT,
            },
        )
        if created:
            student.set_password("student123")
            student.save()
            student.profile.group_name = "ГР-21"
            student.profile.save()

        starts = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + timezone.timedelta(days=2)
        LabSession.objects.get_or_create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            starts_at=starts,
            defaults={
                "ends_at": starts + timezone.timedelta(minutes=90),
                "capacity": 15,
                "status": LabSessionStatus.OPEN,
                "teacher": staff,
            },
        )

        Holiday.objects.get_or_create(date=date(2026, 3, 8), defaults={"name": "8 марта"})

        self.stdout.write(self.style.SUCCESS("Демо-данные загружены."))
        self.stdout.write("Студент: student@stud.spmi.ru / student123")
        self.stdout.write("Сотрудник: staff@spmi.ru / staff123")
