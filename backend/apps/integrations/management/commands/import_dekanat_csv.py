import csv
import re

from django.core.management.base import BaseCommand

from apps.academics.models import Discipline, Semester
from apps.scheduling.models import TrainingCenter
from apps.users.models import User, UserProfile, UserRole


class Command(BaseCommand):
    help = "Импорт данных пилота из CSV (заглушка до API Деканата)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument(
            "--type",
            choices=["students", "teachers", "staff", "disciplines"],
            required=True,
        )
        parser.add_argument(
            "--encoding",
            default="utf-8-sig",
            help="Кодировка CSV (по умолчанию utf-8-sig)",
        )
        parser.add_argument(
            "--delimiter",
            default=",",
            help="Разделитель CSV (по умолчанию запятая)",
        )
        parser.add_argument(
            "--default-password",
            default="changeme123",
            help="Пароль по умолчанию, если в CSV он не передан",
        )
        parser.add_argument(
            "--semester",
            default="Пилот 2026/2027 (нефтегаз)",
            help="Семестр для импортируемых дисциплин (по умолчанию пилотный)",
        )
        parser.add_argument(
            "--generated-domain",
            default="demo.local",
            help="Домен для авто-сгенерированных email (по умолчанию demo.local)",
        )

    @staticmethod
    def _as_bool(value, default=False):
        if value is None:
            return default
        normalized = str(value).strip().lower()
        if not normalized:
            return default
        return normalized in {"1", "true", "yes", "y", "да"}

    @staticmethod
    def _clean(row, key, default=""):
        return str(row.get(key, default) or default).strip()

    def _sanitize_email_local(self, raw: str) -> str:
        candidate = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
        return candidate or "user"

    def _next_generated_email(self, prefix: str) -> str:
        local = self._sanitize_email_local(prefix)
        candidate = f"{local}@{self.generated_domain}"
        suffix = 1
        while User.objects.filter(email=candidate).exists():
            suffix += 1
            candidate = f"{local}-{suffix}@{self.generated_domain}"
        return candidate

    def _resolve_email(self, row, *, role):
        explicit = self._clean(row, "email").lower()
        if explicit:
            return explicit

        if role == UserRole.STUDENT:
            hint = self._clean(row, "student_id") or self._clean(row, "dekanat_id") or self._clean(row, "group")
            return self._next_generated_email(f"student-{hint}")
        if role == UserRole.TEACHER:
            hint = self._clean(row, "last_name") or self._clean(row, "dekanat_id")
            return self._next_generated_email(f"teacher-{hint}")

        hint = self._clean(row, "last_name") or self._clean(row, "dekanat_id")
        return self._next_generated_email(f"staff-{hint}")

    def _upsert_user(self, row, *, role, is_staff, default_password):
        email = self._resolve_email(row, role=role)
        if not email:
            return None, False

        user, created = User.objects.update_or_create(
            email=email,
            defaults={
                "first_name": self._clean(row, "first_name"),
                "last_name": self._clean(row, "last_name"),
                "role": role,
                "is_staff": is_staff,
            },
        )
        password = self._clean(row, "password", default_password) or default_password
        user.set_password(password)
        user.save(update_fields=["password"])
        return user, created

    def handle(self, *args, **options):
        path = options["csv_path"]
        import_type = options["type"]
        encoding = options["encoding"]
        delimiter = options["delimiter"]
        default_password = options["default_password"]
        self.generated_domain = options["generated_domain"]

        created_count = 0
        updated_count = 0
        skipped_count = 0
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                if import_type == "students":
                    created, updated = self._import_student(row, default_password=default_password)
                elif import_type == "teachers":
                    created, updated = self._import_teacher(row, default_password=default_password)
                elif import_type == "staff":
                    created, updated = self._import_staff(row, default_password=default_password)
                elif import_type == "disciplines":
                    created, updated = self._import_discipline(row, semester_name=options["semester"])
                else:
                    created, updated = 0, 0

                if created:
                    created_count += 1
                elif updated:
                    updated_count += 1
                else:
                    skipped_count += 1
        self.stdout.write(self.style.SUCCESS("Импорт завершён."))
        self.stdout.write(f"Создано: {created_count}")
        self.stdout.write(f"Обновлено: {updated_count}")
        self.stdout.write(f"Пропущено: {skipped_count}")

    def _import_student(self, row, *, default_password):
        user, created = self._upsert_user(
            row,
            role=UserRole.STUDENT,
            is_staff=False,
            default_password=default_password,
        )
        if not user:
            return 0, 0
        UserProfile.objects.filter(user=user).update(
            group_name=self._clean(row, "group"),
            dekanat_id=self._clean(row, "dekanat_id"),
            student_id=self._clean(row, "student_id"),
            faculty=self._clean(row, "faculty"),
            gender=self._clean(row, "gender"),
            phone=self._clean(row, "phone"),
        )
        return int(created), int(not created)

    def _import_teacher(self, row, *, default_password):
        user, created = self._upsert_user(
            row,
            role=UserRole.TEACHER,
            is_staff=self._as_bool(row.get("is_staff"), default=False),
            default_password=default_password,
        )
        if not user:
            return 0, 0
        training_center_number = self._clean(row, "training_center_number")
        if training_center_number.isdigit():
            training_center = TrainingCenter.objects.filter(number=int(training_center_number)).first()
            if training_center:
                user.profile.training_center = training_center
                user.profile.save(update_fields=["training_center"])
        return int(created), int(not created)

    def _import_staff(self, row, *, default_password):
        role = self._clean(row, "role", UserRole.LAB_ADMIN)
        if role not in {UserRole.LAB_ADMIN, UserRole.SYS_ADMIN}:
            role = UserRole.LAB_ADMIN
        user, created = self._upsert_user(
            row,
            role=role,
            is_staff=self._as_bool(row.get("is_staff"), default=True),
            default_password=default_password,
        )
        if not user:
            return 0, 0

        training_center_number = self._clean(row, "training_center_number")
        if training_center_number.isdigit():
            training_center = TrainingCenter.objects.filter(number=int(training_center_number)).first()
            if training_center:
                user.profile.training_center = training_center
                user.profile.save(update_fields=["training_center"])
        return int(created), int(not created)

    def _import_discipline(self, row, *, semester_name):
        title = self._clean(row, "title")
        if not title:
            return 0, 0
        code = self._clean(row, "code")

        semester = Semester.objects.filter(name=semester_name).first()
        if semester is None:
            semester = Semester.objects.filter(is_active=True).first()

        defaults = {
            "title": title,
            "semester": semester,
            "dekanat_id": self._clean(row, "dekanat_id"),
            "description": self._clean(row, "description"),
            "is_published": self._as_bool(row.get("is_published"), default=True),
        }
        if code:
            discipline, created = Discipline.objects.update_or_create(code=code, defaults=defaults)
        else:
            discipline, created = Discipline.objects.update_or_create(title=title, defaults=defaults)
        if not discipline.code:
            discipline.code = f"DISC-{discipline.id}"
            discipline.save(update_fields=["code"])
        return int(created), int(not created)
