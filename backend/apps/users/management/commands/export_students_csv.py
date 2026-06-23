import csv
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.users.models import User, UserRole


class Command(BaseCommand):
    help = "Экспорт логинов студентов и групп в CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "output",
            nargs="?",
            default="-",
            help="Путь к CSV-файлу или '-' для stdout (по умолчанию: -)",
        )

    def handle(self, *args, **options):
        students = (
            User.objects.filter(role=UserRole.STUDENT)
            .select_related("profile", "profile__student_group")
            .order_by("profile__group_name", "last_name", "first_name")
        )

        rows = []
        for user in students:
            profile = user.profile
            group = profile.group_name or (
                profile.student_group.name if profile.student_group_id else ""
            )
            rows.append(
                {
                    "email": user.email,
                    "group": group,
                    "last_name": user.last_name,
                    "first_name": user.first_name,
                    "student_id": profile.student_id,
                }
            )

        fieldnames = ["email", "group", "last_name", "first_name", "student_id"]
        output = options["output"]
        if output == "-":
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            return

        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"Экспортировано студентов: {len(rows)} -> {path}"))
