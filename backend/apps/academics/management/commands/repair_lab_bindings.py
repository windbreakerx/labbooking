from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.academics.models import Discipline, LabWork, Semester
from apps.scheduling.models import TrainingCenter


class Command(BaseCommand):
    help = (
        "Привязать дисциплины и лабораторные работы без training_centers к УЦ. "
        "Нужно после добавления дисциплин через админку до scoping по лабораториям."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tc-number",
            type=int,
            default=1,
            help="Номер учебного центра (лаборатории), по умолчанию 1.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет привязано.",
        )

    def handle(self, *args, **options):
        tc = TrainingCenter.objects.filter(number=options["tc_number"]).first()
        if not tc:
            self.stderr.write(self.style.ERROR(f"УЦ №{options['tc_number']} не найден."))
            return

        semester = Semester.objects.filter(is_active=True).first()
        if not semester:
            self.stderr.write(self.style.WARNING("Нет активного семестра — привязка ко всем дисциплинам без УЦ."))

        discipline_qs = Discipline.objects.annotate(tc_count=Count("training_centers")).filter(tc_count=0)
        if semester:
            discipline_qs = discipline_qs.filter(semester=semester)

        linked_disciplines = 0
        for discipline in discipline_qs.order_by("title"):
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] дисциплина: {discipline.title}")
            else:
                discipline.training_centers.add(tc)
                if not discipline.code:
                    discipline.code = f"DISC-{discipline.pk}"
                    discipline.save(update_fields=["code"])
                self.stdout.write(f"Привязана дисциплина: {discipline.title}")
            linked_disciplines += 1

        linked_lab_works = 0
        lab_work_qs = (
            LabWork.objects.annotate(tc_count=Count("training_centers"))
            .filter(tc_count=0, disciplines__training_centers=tc)
            .prefetch_related("disciplines")
            .distinct()
        )
        for lab_work in lab_work_qs.order_by("number", "title"):
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] ЛР: {lab_work}")
            else:
                lab_work.training_centers.add(tc)
                self.stdout.write(f"Привязана ЛР: {lab_work}")
            linked_lab_works += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: дисциплин {linked_disciplines}, лабораторных работ {linked_lab_works} "
                f"(УЦ №{tc.number})."
            )
        )
