"""Import department workload draft CSV catalogs."""

from __future__ import annotations

import csv
from pathlib import Path

from django.db import transaction

from apps.academics.models import ALLOWED_LAB_DURATIONS, Department, Discipline, Faculty, LabWork, Semester, StudentGroup
from apps.academics.services.catalog_normalize import lab_work_match_key, normalize_lab_title
from apps.scheduling.models import Laboratory, Room, TrainingCenter

KNOWN_DRAFTS = (
    "metallurgy_draft",
    "otf_draft",
    "htpe_draft",
    "ofh_draft",
    "opi_draft",
    "bp_draft",
    "vd_draft",
)

FALLBACK_LABORATORY_NAMES: dict[tuple[str, int], str] = {
    ("ФПМС", 1): "Комплексная учебная лаборатория факультета переработки минерального сырья",
    ("ФПМС", 3): "Многофункциональная учебная лаборатория общей химии в Инженерном корпусе",
    ("ИБИО", 3): "Комплексная учебная лаборатория общей физики",
    ("ГФ", 2): "Учебная лаборатория кафедры безопасности производств",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _clean(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _parse_int(value: str) -> int | None:
    if not value or not str(value).strip().isdigit():
        return None
    return int(str(value).strip())


def _normalize_duration(value: str) -> int:
    minutes = _parse_int(value)
    if not minutes:
        return 90
    if minutes in ALLOWED_LAB_DURATIONS:
        return minutes
    return min(ALLOWED_LAB_DURATIONS, key=lambda item: abs(item - minutes))


def _load_department_lab_map(studlab_dir: Path) -> dict[str, Laboratory]:
    path = studlab_dir / "04_laboratories.csv"
    if not path.is_file():
        return {}
    mapping: dict[str, Laboratory] = {}
    for row in _read_csv(path):
        dept_code = _clean(row, "department_code_suggested")
        lab_name = _clean(row, "lab_name_full")
        if not dept_code or not lab_name:
            continue
        laboratory = Laboratory.objects.filter(name=lab_name).first()
        if laboratory:
            mapping[dept_code] = laboratory
    return mapping


def _resolve_laboratory(
  *,
    department_code: str,
    faculty_code: str,
    training_center: TrainingCenter,
    dept_lab_map: dict[str, Laboratory],
) -> Laboratory | None:
    if department_code in dept_lab_map:
        return dept_lab_map[department_code]
    fallback_name = FALLBACK_LABORATORY_NAMES.get((faculty_code, training_center.number))
    if fallback_name:
        laboratory = Laboratory.objects.filter(
            training_center=training_center,
            name=fallback_name,
        ).first()
        if laboratory:
            return laboratory
    return Laboratory.objects.filter(training_center=training_center).order_by("name").first()


def _find_lab_work(title: str, room: Room | None) -> LabWork | None:
    room_id = room.pk if room else None
    target_key = lab_work_match_key(title, room_id)
    for lab_work in LabWork.objects.select_related("default_room").filter(
        title__isnull=False,
    ):
        if lab_work_match_key(lab_work.title, lab_work.default_room_id) == target_key:
            return lab_work
    if room is None:
        return LabWork.objects.filter(title=title, default_room__isnull=True).first()
    return None


@transaction.atomic
def import_department_draft(
    draft_dir: Path,
    *,
    semester: Semester,
    studlab_dir: Path,
) -> dict[str, int]:
    stats = {
        "disciplines": 0,
        "lab_works": 0,
        "groups": 0,
        "curriculum_links": 0,
        "lab_group_links": 0,
    }
    dept_rows = _read_csv(draft_dir / "01_department.csv")
    if not dept_rows:
        return stats
    dept_row = dept_rows[0]
    faculty_code = _clean(dept_row, "faculty_code")
    department_code = _clean(dept_row, "department_code")
    tc_number = _parse_int(_clean(dept_row, "default_training_center")) or 1

    faculty = Faculty.objects.filter(code=faculty_code).first()
    department = Department.objects.filter(short_code=department_code).first()
    training_center, _ = TrainingCenter.objects.get_or_create(
        number=tc_number,
        defaults={"name": f"Учебный центр №{tc_number}"},
    )
    dept_lab_map = _load_department_lab_map(studlab_dir)
    laboratory = _resolve_laboratory(
        department_code=department_code,
        faculty_code=faculty_code,
        training_center=training_center,
        dept_lab_map=dept_lab_map,
    )

    discipline_by_code: dict[str, Discipline] = {}
    discipline_by_title: dict[str, Discipline] = {}
    for row in _read_csv(draft_dir / "02_disciplines.csv"):
        code = _clean(row, "discipline_code_suggested")
        title = _clean(row, "discipline_title")
        if not code or not title:
            continue
        discipline, created = Discipline.objects.update_or_create(
            code=code,
            defaults={
                "title": title,
                "semester": semester,
                "department": department,
                "is_published": True,
            },
        )
        discipline.training_centers.add(training_center)
        if laboratory:
            discipline.laboratories.add(laboratory)
        discipline_by_code[code] = discipline
        discipline_by_title[title] = discipline
        if created:
            stats["disciplines"] += 1

    lab_by_key: dict[tuple[str, int | None], LabWork] = {}
    for row in _read_csv(draft_dir / "07_lab_works_unique.csv"):
        title = _clean(row, "lab_title")
        discipline_title = _clean(row, "discipline_title")
        if not title or not discipline_title:
            continue
        discipline = discipline_by_title.get(discipline_title)
        if not discipline:
            continue
        room_number = _clean(row, "room_number")
        room = None
        if room_number:
            room, _ = Room.objects.get_or_create(
                training_center=training_center,
                number=room_number,
                defaults={"capacity": _parse_int(_clean(row, "capacity")) or 30},
            )
            if laboratory and room.laboratory_id is None:
                room.laboratory = laboratory
                room.save(update_fields=["laboratory"])

        key = lab_work_match_key(title, room.pk if room else None)
        lab_work = lab_by_key.get(key) or _find_lab_work(title, room)
        capacity = _parse_int(_clean(row, "capacity")) or 30
        duration = _normalize_duration(_clean(row, "duration_minutes"))
        if lab_work is None:
            next_number = (
                LabWork.objects.order_by("-number").values_list("number", flat=True).first() or 0
            ) + 1
            lab_work = LabWork.objects.create(
                number=next_number,
                title=title,
                duration_minutes=duration,
                capacity=capacity,
                default_room=room,
                is_published=True,
                code=f"{department_code}-LR-{next_number:04d}",
            )
            stats["lab_works"] += 1
        else:
            changed_fields = []
            if room and lab_work.default_room_id != room.id:
                lab_work.default_room = room
                changed_fields.append("default_room")
            if duration and lab_work.duration_minutes != duration:
                lab_work.duration_minutes = duration
                changed_fields.append("duration_minutes")
            if capacity and lab_work.capacity != capacity:
                lab_work.capacity = capacity
                changed_fields.append("capacity")
            if changed_fields:
                lab_work.save(update_fields=changed_fields)

        lab_work.disciplines.add(discipline)
        lab_work.training_centers.add(training_center)
        if laboratory:
            lab_work.laboratories.add(laboratory)
        lab_by_key[key] = lab_work

    group_cache: dict[str, StudentGroup] = {}
    for row in _read_csv(draft_dir / "03_groups.csv"):
        group_name = _clean(row, "group_name")
        if not group_name:
            continue
        group, created = StudentGroup.objects.get_or_create(
            name=group_name,
            defaults={
                "faculty": faculty.title if faculty else _clean(dept_row, "faculty_title"),
                "department": department,
            },
        )
        if department and group.department_id is None:
            group.department = department
            group.save(update_fields=["department"])
        group_cache[group_name] = group
        if created:
            stats["groups"] += 1

    seen_curriculum: set[tuple[str, str]] = set()
    for row in _read_csv(draft_dir / "05_curriculum.csv"):
        group_name = _clean(row, "group_name")
        code = _clean(row, "discipline_code_suggested")
        if not group_name or not code:
            continue
        group = group_cache.get(group_name) or StudentGroup.objects.filter(name=group_name).first()
        discipline = discipline_by_code.get(code)
        if not group or not discipline:
            continue
        key = (group_name, code)
        if key in seen_curriculum:
            continue
        seen_curriculum.add(key)
        if not group.disciplines.filter(pk=discipline.pk).exists():
            group.disciplines.add(discipline)
            stats["curriculum_links"] += 1

    seen_lab_links: set[tuple[str, int]] = set()
    for row in _read_csv(draft_dir / "04_lab_works.csv"):
        group_name = _clean(row, "group_name")
        title = _clean(row, "lab_title")
        discipline_title = _clean(row, "discipline_title")
        if not group_name or not title:
            continue
        group = group_cache.get(group_name) or StudentGroup.objects.filter(name=group_name).first()
        if not group:
            continue
        room_number = _clean(row, "room_number")
        room = None
        if room_number:
            room = Room.objects.filter(training_center=training_center, number=room_number).first()
        lab_work = lab_by_key.get(lab_work_match_key(title, room.pk if room else None))
        if lab_work is None:
            lab_work = _find_lab_work(title, room)
        if not lab_work:
            continue
        link_key = (group_name, lab_work.pk)
        if link_key in seen_lab_links:
            continue
        seen_lab_links.add(link_key)
        if discipline_title:
            discipline = discipline_by_title.get(discipline_title)
            if discipline and not group.disciplines.filter(pk=discipline.pk).exists():
                group.disciplines.add(discipline)
        if not group.lab_works.filter(pk=lab_work.pk).exists():
            group.lab_works.add(lab_work)
            stats["lab_group_links"] += 1

    return stats


def import_all_drafts(
    templates_dir: Path,
    *,
    semester_name: str,
    studlab_dir: Path,
    only: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    semester = Semester.objects.filter(name=semester_name).first()
    if semester is None:
        semester = Semester.objects.filter(is_active=True).first()
    if semester is None:
        raise ValueError(f"Семестр не найден: {semester_name}")

    results: dict[str, dict[str, int]] = {}
    draft_names = only or list(KNOWN_DRAFTS)
    for draft_name in draft_names:
        draft_dir = templates_dir / draft_name
        if not (draft_dir / "01_department.csv").is_file():
            continue
        results[draft_name] = import_department_draft(
            draft_dir,
            semester=semester,
            studlab_dir=studlab_dir,
        )
    return results
