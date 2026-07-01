from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.academics.services.workload_students import (
    DEFAULT_ACADEMIC_YEAR,
    DEFAULT_MAX_STUDENTS_PER_GROUP,
    collect_group_targets,
    generate_workload_students,
)


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
        parser.add_argument(
            "--academic-year",
            default=DEFAULT_ACADEMIC_YEAR,
            help="Брать только группы из листов с этим учебным годом (пусто — все годы)",
        )
        parser.add_argument(
            "--max-per-group",
            type=int,
            default=DEFAULT_MAX_STUDENTS_PER_GROUP,
            help="Потолок численности группы (в Excel иногда попадают 285 и др.)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, сколько студентов будет создано",
        )

    def handle(self, *args, **options):
        templates_dir = Path(options["templates_dir"])
        if not templates_dir.is_dir():
            raise CommandError(f"Каталог не найден: {templates_dir}")

        academic_year = options["academic_year"] or None
        max_per_group = options["max_per_group"]

        if options["dry_run"]:
            targets = collect_group_targets(
                templates_dir,
                academic_year=academic_year,
                max_per_group=max_per_group,
            )
            self.stdout.write(f"groups: {len(targets)}")
            self.stdout.write(f"target_students: {sum(targets.values())}")
            return

        stats = generate_workload_students(
            templates_dir,
            default_password=options["default_password"],
            skip_existing_groups=not options["include_existing_groups"],
            academic_year=academic_year,
            max_per_group=max_per_group,
        )
        self.stdout.write(self.style.SUCCESS("Генерация студентов завершена."))
        for key, value in stats.items():
            self.stdout.write(f"{key}: {value}")
