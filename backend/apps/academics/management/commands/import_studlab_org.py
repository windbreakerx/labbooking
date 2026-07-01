from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.academics.services.studlab_import import import_studlab_draft


class Command(BaseCommand):
    help = "Импорт оргструктуры из docs/csv_templates/studlab_draft."

    def add_arguments(self, parser):
        parser.add_argument(
            "draft_dir",
            nargs="?",
            default="docs/csv_templates/studlab_draft",
            help="Каталог с 01_faculties.csv … 06_staff.csv",
        )
        parser.add_argument(
            "--default-password",
            default="changeme123",
            help="Пароль для импортированных сотрудников (по умолчанию changeme123)",
        )

    def handle(self, *args, **options):
        draft_dir = Path(options["draft_dir"])
        if not (draft_dir / "04_laboratories.csv").is_file():
            raise CommandError(f"Не найден studlab draft: {draft_dir}")
        stats = import_studlab_draft(
            draft_dir,
            default_password=options["default_password"],
        )
        self.stdout.write(self.style.SUCCESS("Studlab import завершён."))
        for key, value in stats.items():
            self.stdout.write(f"{key}: {value}")
