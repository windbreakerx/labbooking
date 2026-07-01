from django.core.management.base import BaseCommand

from apps.academics.services.lab_work_dedupe import dedupe_lab_works


class Command(BaseCommand):
    help = "Объединить дублирующиеся лабораторные работы (одинаковое название и аудитория)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, сколько дублей будет объединено",
        )

    def handle(self, *args, **options):
        stats = dedupe_lab_works(dry_run=options["dry_run"])
        mode = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Групп дублей: {stats['duplicate_groups']}, "
                f"объединено записей: {stats['merged_rows']}{mode}"
            )
        )
