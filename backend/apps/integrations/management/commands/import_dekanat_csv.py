import csv

from django.core.management.base import BaseCommand

from apps.academics.models import Discipline, Semester
from apps.users.models import User, UserProfile, UserRole


class Command(BaseCommand):
    help = "Импорт студентов/преподавателей/дисциплин из CSV (заглушка до API Деканата)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument(
            "--type",
            choices=["students", "teachers", "disciplines"],
            required=True,
        )

    def handle(self, *args, **options):
        path = options["csv_path"]
        import_type = options["type"]
        count = 0
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if import_type == "students":
                    count += self._import_student(row)
                elif import_type == "teachers":
                    count += self._import_teacher(row)
                elif import_type == "disciplines":
                    count += self._import_discipline(row)
        self.stdout.write(self.style.SUCCESS(f"Импортировано: {count}"))

    def _import_student(self, row) -> int:
        email = row.get("email", "").strip()
        if not email or User.objects.filter(email=email).exists():
            return 0
        user = User.objects.create_user(
            email=email,
            password=row.get("password", "changeme"),
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            role=UserRole.STUDENT,
        )
        UserProfile.objects.filter(user=user).update(
            group_name=row.get("group", ""),
            dekanat_id=row.get("dekanat_id", ""),
        )
        return 1

    def _import_teacher(self, row) -> int:
        email = row.get("email", "").strip()
        if not email or User.objects.filter(email=email).exists():
            return 0
        User.objects.create_user(
            email=email,
            password=row.get("password", "changeme"),
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            role=UserRole.TEACHER,
        )
        return 1

    def _import_discipline(self, row) -> int:
        title = row.get("title", "").strip()
        if not title:
            return 0
        semester = Semester.objects.filter(is_active=True).first()
        Discipline.objects.get_or_create(
            title=title,
            defaults={
                "code": row.get("code", ""),
                "semester": semester,
                "dekanat_id": row.get("dekanat_id", ""),
            },
        )
        return 1
