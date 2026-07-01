from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.academics.services.workload_students import generate_workload_students


class Command(BaseCommand):
    help = "Создать студентов по численности групп из workload draft CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--templates-dir",
            default="docs/csv_templates",
            help="Корень с папками *_draft",
        )
        parser.add_argument(
            "--default-password",
            default="student123",
            help="Пароль для новых студентов",
        )
        parser.add_argument(
            "--include-existing-groups",
            action="store_true",
            help="Догенерировать студентов даже для групп, где уже есть аккаунты",
        )

    def handle(self, *args, **options):
        templates_dir = Path(options["templates_dir"])
        if not templates_dir.is_dir():
            raise CommandError(f"Каталог не найден: {templates_dir}")

        stats = generate_workload_students(
            templates_dir,
            default_password=options["default_password"],
            skip_existing_groups=not options["include_existing_groups"],
        )
        self.stdout.write(self.style.SUCCESS("Генерация студентов завершена."))
        for key, value in stats.items():
            self.stdout.write(f"{key}: {value}")
