"""Импорт данных из Excel-журналов ЛР_учет в БД."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.academics.models import ALLOWED_LAB_DURATIONS, Discipline, LabWork, Semester, StudentGroup
from apps.bookings.models import Booking
from apps.integrations.lr_accounting.names import DisplayName, shuffle_student_display_names
from apps.integrations.lr_accounting.parser import ParsedLabWork, ParsedStudent, ParsedWorkbook, parse_workbook
from apps.integrations.lr_accounting.students import (
    allocate_student_id,
    new_year_counters,
    student_email,
)
from apps.scheduling.models import LabSession, LabStand, Laboratory, ScheduleEntry, Room, TrainingCenter
from apps.users.models import User, UserProfile, UserRole

ROOMS_PAYLOAD = [
    ("1123", 10),
    ("1124", 15),
    ("2105", 21),
    ("2111", 15),
    ("2112", 20),
    ("2113", 15),
    ("2114", 5),
    ("2115", 21),
    ("2116", 16),
    ("2117", 15),
    ("2118", 5),
    ("3314", 14),
    ("3316", 15),
    ("3420", 24),
    ("3428", 44),
]

DEFAULT_SEMESTER_NAME = "Весна 2025/2026"


class Command(BaseCommand):
    help = "Импорт дисциплин, ЛР, групп и студентов из Excel-журналов ЛР_учет"

    def add_arguments(self, parser):
        parser.add_argument(
            "labs_dir",
            nargs="?",
            default="",
            help="Каталог с файлами ЛР_учет *.xlsx",
        )
        parser.add_argument(
            "--semester",
            default=DEFAULT_SEMESTER_NAME,
            help="Название семестра (по умолчанию: Весна 2025/2026)",
        )
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Удалить пилотные/старые дисциплины, ЛР, группы, студентов и записи перед импортом",
        )
        parser.add_argument(
            "--default-password",
            default="student123",
            help="Пароль для создаваемых студентов",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет импортировано",
        )
        parser.add_argument(
            "--no-shuffle-names",
            action="store_true",
            help="Не перемешивать ФИО студентов (только подставить синтетические отчества)",
        )
        parser.add_argument(
            "--shuffle-seed",
            type=int,
            default=None,
            help="Seed для перемешивания ФИО (для воспроизводимости)",
        )
        parser.add_argument(
            "--default-capacity",
            type=int,
            default=3,
            help="Емкость ЛР по умолчанию при импорте (по умолчанию: 3)",
        )

    def handle(self, *args, **options):
        labs_dir = Path(options["labs_dir"] or "").expanduser()
        if not labs_dir.is_dir():
            raise CommandError(f"Каталог не найден: {labs_dir}")

        files = sorted(labs_dir.glob("ЛР_учет*.xlsx"))
        if not files:
            raise CommandError(f"В каталоге {labs_dir} нет файлов ЛР_учет*.xlsx")

        workbooks = [parse_workbook(path) for path in files]
        if options["dry_run"]:
            self._print_dry_run(workbooks)
            return

        with transaction.atomic():
            if options["clear_existing"]:
                self._clear_existing_data()
            training_center = self._ensure_training_center()
            laboratory = self._ensure_laboratory(training_center)
            rooms = self._ensure_rooms(training_center)
            semester = self._ensure_semester(options["semester"])
            stats = self._import_workbooks(
                workbooks,
                semester=semester,
                training_center=training_center,
                laboratory=laboratory,
                rooms=rooms,
                default_password=options["default_password"],
                shuffle_names=not options["no_shuffle_names"],
                shuffle_seed=options["shuffle_seed"],
                default_capacity=options["default_capacity"],
            )

        self.stdout.write(self.style.SUCCESS("Импорт завершён."))
        for key, value in stats.items():
            self.stdout.write(f"{key}: {value}")

    def _print_dry_run(self, workbooks: list[ParsedWorkbook]):
        for workbook in workbooks:
            students = sum(len(group.students) for group in workbook.group_sheets)
            self.stdout.write(
                f"{workbook.source_file} -> ауд. {workbook.room_number}: "
                f"{len(workbook.group_sheets)} групп, {students} студентов, "
                f"{len(workbook.catalog)} позиций в перечне"
            )

    def _clear_existing_data(self):
        Booking.objects.all().delete()
        LabSession.objects.all().delete()
        ScheduleEntry.objects.all().delete()
        LabStand.objects.all().delete()
        User.objects.filter(role=UserRole.STUDENT).delete()
        User.objects.filter(role=UserRole.TEACHER, email__endswith="@spmi.ru").delete()
        StudentGroup.objects.all().delete()
        LabWork.objects.all().delete()
        Discipline.objects.all().delete()
        Semester.objects.all().delete()
        self.stdout.write("Старые учебные данные удалены (завлаб и сотрудники сохранены).")

    def _ensure_training_center(self) -> TrainingCenter:
        training_center, _ = TrainingCenter.objects.update_or_create(
            number=1,
            defaults={"name": "Комплексная учебная лаборатория нефтегазового факультета"},
        )
        return training_center

    def _ensure_laboratory(self, training_center: TrainingCenter) -> Laboratory:
        laboratory, _ = Laboratory.objects.update_or_create(
            training_center=training_center,
            name="Комплексная учебная лаборатория нефтегазового факультета",
        )
        return laboratory

    def _ensure_rooms(self, training_center: TrainingCenter) -> dict[str, Room]:
        rooms: dict[str, Room] = {}
        for room_number, capacity in ROOMS_PAYLOAD:
            room, _ = Room.objects.update_or_create(
                training_center=training_center,
                number=room_number,
                defaults={"capacity": capacity},
            )
            rooms[room_number] = room
        return rooms

    def _ensure_semester(self, name: str) -> Semester:
        Semester.objects.update(is_active=False)
        semester, _ = Semester.objects.update_or_create(
            name=name,
            defaults={
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 6, 30),
                "is_active": True,
            },
        )
        return semester

    def _import_workbooks(
        self,
        workbooks: list[ParsedWorkbook],
        *,
        semester: Semester,
        training_center: TrainingCenter,
        laboratory: Laboratory,
        rooms: dict[str, Room],
        default_password: str,
        shuffle_names: bool = True,
        shuffle_seed: int | None = None,
        default_capacity: int = 3,
    ) -> dict[str, int]:
        stats = {
            "disciplines": 0,
            "lab_works": 0,
            "groups": 0,
            "students": 0,
            "stands": 0,
        }
        discipline_cache: dict[str, Discipline] = {}
        lab_cache: dict[tuple[str, str], LabWork] = {}
        group_cache: dict[str, StudentGroup] = {}
        year_counters = new_year_counters()
        display_name_map = self._build_display_name_map(
            workbooks,
            shuffle_names=shuffle_names,
            shuffle_seed=shuffle_seed,
        )
        def get_discipline(title: str) -> Discipline | None:
            title = title.strip()
            if not title:
                return None
            if title in discipline_cache:
                return discipline_cache[title]
            discipline, created = Discipline.objects.get_or_create(
                title=title,
                semester=semester,
                defaults={
                    "code": self._discipline_code(title),
                    "is_published": True,
                },
            )
            discipline.training_centers.add(training_center)
            discipline.laboratories.add(laboratory)
            discipline_cache[title] = discipline
            if created:
                stats["disciplines"] += 1
            return discipline

        def upsert_lab(
            *,
            discipline_title: str,
            parsed_lab: ParsedLabWork,
            room: Room,
        ) -> LabWork | None:
            discipline = get_discipline(discipline_title)
            if discipline is None:
                return None
            cache_key = (discipline.title, parsed_lab.title)
            if cache_key in lab_cache:
                lab_work = lab_cache[cache_key]
                changed = False
                if lab_work.default_room_id != room.id:
                    lab_work.default_room = room
                    changed = True
                normalized_duration = self._normalize_duration(parsed_lab.duration_minutes)
                if normalized_duration and lab_work.duration_minutes != normalized_duration:
                    lab_work.duration_minutes = normalized_duration
                    changed = True
                imported_capacity = min(default_capacity, room.capacity)
                if lab_work.capacity != imported_capacity:
                    lab_work.capacity = imported_capacity
                    changed = True
                if changed:
                    lab_work.save(update_fields=["default_room", "duration_minutes", "capacity"])
                return lab_work

            existing = LabWork.objects.filter(discipline=discipline, title=parsed_lab.title).first()
            if existing:
                lab_work = existing
            else:
                next_number = (
                    LabWork.objects.filter(discipline=discipline).order_by("-number").values_list("number", flat=True).first()
                    or 0
                ) + 1
                lab_work = LabWork.objects.create(
                    discipline=discipline,
                    number=parsed_lab.catalog_number or next_number,
                    title=parsed_lab.title,
                    duration_minutes=self._normalize_duration(parsed_lab.duration_minutes) or 90,
                    capacity=min(default_capacity, room.capacity),
                    default_room=room,
                    is_published=True,
                )
                stats["lab_works"] += 1
            lab_work.training_centers.add(training_center)
            lab_work.laboratories.add(laboratory)
            if lab_work.default_room_id != room.id:
                lab_work.default_room = room
                lab_work.save(update_fields=["default_room"])
            lab_cache[cache_key] = lab_work
            return lab_work

        for workbook in workbooks:
            room = rooms.get(workbook.room_number)
            if room is None:
                raise CommandError(f"Аудитория {workbook.room_number} не найдена для {workbook.source_file}")

            for group_sheet in workbook.group_sheets:
                student_group = group_cache.get(group_sheet.name)
                if student_group is None:
                    student_group, created = StudentGroup.objects.get_or_create(
                        name=group_sheet.name,
                        defaults={"faculty": "Нефтегазовый"},
                    )
                    group_cache[group_sheet.name] = student_group
                    if created:
                        stats["groups"] += 1

                for parsed_lab in group_sheet.lab_works:
                    if not parsed_lab.discipline:
                        continue
                    lab_work = upsert_lab(
                        discipline_title=parsed_lab.discipline,
                        parsed_lab=parsed_lab,
                        room=room,
                    )
                    if lab_work:
                        student_group.disciplines.add(lab_work.discipline)
                        student_group.lab_works.add(lab_work)

                for student in group_sheet.students:
                    record_id = allocate_student_id(group_sheet.name, year_counters)
                    email = student_email(record_id)
                    display_name = display_name_map[(group_sheet.name, student.number)]
                    user, created = User.objects.update_or_create(
                        email=email,
                        defaults={
                            "first_name": display_name.first_name,
                            "last_name": display_name.last_name,
                            "role": UserRole.STUDENT,
                            "is_staff": False,
                        },
                    )
                    user.set_password(default_password)
                    user.save(update_fields=["password"])
                    UserProfile.objects.filter(user=user).update(
                        group_name=group_sheet.name,
                        student_group=student_group,
                        faculty="Нефтегазовый",
                        student_id=record_id,
                    )
                    if created:
                        stats["students"] += 1

            for parsed_lab in workbook.catalog:
                discipline_title = parsed_lab.discipline
                if not discipline_title:
                    existing = LabWork.objects.filter(title=parsed_lab.title, default_room=room).first()
                    if existing:
                        discipline_title = existing.discipline.title
                    else:
                        continue
                lab_work = upsert_lab(discipline_title=discipline_title, parsed_lab=parsed_lab, room=room)
                if lab_work and parsed_lab.stand_name:
                    stand, created = LabStand.objects.update_or_create(
                        name=parsed_lab.stand_name,
                        training_center=training_center,
                        room=room,
                        defaults={
                            "inventory_number": f"LR-{lab_work.id:05d}",
                            "description": lab_work.title[:250],
                        },
                    )
                    if created:
                        stats["stands"] += 1
                    if lab_work.primary_stand_id != stand.id:
                        lab_work.primary_stand = stand
                        lab_work.save(update_fields=["primary_stand"])

        return stats

    def _build_display_name_map(
        self,
        workbooks: list[ParsedWorkbook],
        *,
        shuffle_names: bool,
        shuffle_seed: int | None,
    ) -> dict[tuple[str, int], DisplayName]:
        entries: list[tuple[str, ParsedStudent]] = []
        for workbook in workbooks:
            for group_sheet in workbook.group_sheets:
                for student in group_sheet.students:
                    entries.append((group_sheet.name, student))

        if shuffle_names:
            shuffled = shuffle_student_display_names(
                [student for _, student in entries],
                seed=shuffle_seed,
            )
            return {
                (group_name, student.number): display_name
                for (group_name, student), display_name in zip(entries, shuffled, strict=True)
            }

        from apps.integrations.lr_accounting.names import (
            FALLBACK_FEMALE_PATRONYMICS,
            FALLBACK_MALE_PATRONYMICS,
            infer_gender,
            split_name_parts,
        )

        display_name_map: dict[tuple[str, int], DisplayName] = {}
        patronymic_index = 0
        for group_name, student in entries:
            last_name, first, patronymic = split_name_parts(student)
            gender = infer_gender(first=first, patronymic=patronymic, last_name=last_name)
            if not patronymic:
                pool = FALLBACK_FEMALE_PATRONYMICS if gender == "female" else FALLBACK_MALE_PATRONYMICS
                patronymic = pool[patronymic_index % len(pool)]
                patronymic_index += 1
            first_name = f"{first} {patronymic}".strip()
            display_name_map[(group_name, student.number)] = DisplayName(
                first_name=first_name,
                last_name=last_name,
            )
        return display_name_map

    @staticmethod
    def _discipline_code(title: str) -> str:
        slug = slugify(title, allow_unicode=False)
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        return (slug[:24] or "discipline").upper()

    def _normalize_duration(self, duration: int | None) -> int | None:
        if duration is None:
            return None
        if duration in ALLOWED_LAB_DURATIONS:
            return duration
        nearest = min(ALLOWED_LAB_DURATIONS, key=lambda value: abs(value - duration))
        self.stdout.write(
            self.style.WARNING(
                f"Длительность {duration} мин заменена на допустимое значение {nearest} мин."
            )
        )
        return nearest
