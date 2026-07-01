from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.academics.services.curated_catalog_import import KNOWN_DRAFTS, import_all_drafts


class Command(BaseCommand):
    help = "Импорт каталога дисциплин/ЛР/учебных планов из docs/csv_templates/*_draft."

    def add_arguments(self, parser):
        parser.add_argument(
            "--templates-dir",
            default="docs/csv_templates",
            help="Корень с папками metallurgy_draft, otf_draft, …",
        )
        parser.add_argument(
            "--studlab-dir",
            default="docs/csv_templates/studlab_draft",
            help="Каталог studlab для привязки лабораторий к кафедрам",
        )
        parser.add_argument(
            "--semester",
            default="Весна 2025/2026",
            help="Семестр для дисциплин",
        )
        parser.add_argument(
            "--department",
            action="append",
            dest="departments",
            choices=KNOWN_DRAFTS,
            help="Импортировать только указанные draft-папки (можно повторять)",
        )

    def handle(self, *args, **options):
        templates_dir = Path(options["templates_dir"])
        studlab_dir = Path(options["studlab_dir"])
        if not templates_dir.is_dir():
            raise CommandError(f"Каталог не найден: {templates_dir}")
        try:
            results = import_all_drafts(
                templates_dir,
                semester_name=options["semester"],
                studlab_dir=studlab_dir,
                only=options["departments"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Импорт каталога завершён."))
        for draft_name, stats in results.items():
            self.stdout.write(f"\n{draft_name}:")
            for key, value in stats.items():
                self.stdout.write(f"  {key}: {value}")
