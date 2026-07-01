"""Import normalized studlab draft CSVs into Django models."""

from __future__ import annotations

import csv
from pathlib import Path

from django.db import transaction

from apps.academics.models import Department, Faculty
from apps.scheduling.models import Laboratory, LaboratoryType, Room, TrainingCenter
from apps.users.models import User, UserProfile, UserRole


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _clean(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _truncate(value: str, max_length: int) -> str:
    return value[:max_length] if value else value


def _lab_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized in LaboratoryType.values:
        return normalized
    return LaboratoryType.REGULAR


def _upsert_department(
    *,
    code: str,
    title: str,
    faculty: Faculty | None,
) -> tuple[Department, bool]:
    """Сопоставить по short_code или title — title уникален в БД."""
    department = Department.objects.filter(short_code=code).first()
    if department is None:
        department = Department.objects.filter(title=title).first()
    if department is None:
        return Department.objects.create(
            short_code=code,
            title=title,
            faculty=faculty,
        ), True

    update_fields: list[str] = []
    if code and department.short_code != code:
        department.short_code = code
        update_fields.append("short_code")
    if faculty is not None and department.faculty_id != faculty.pk:
        department.faculty = faculty
        update_fields.append("faculty")
    if update_fields:
        department.save(update_fields=update_fields)
    return department, False


@transaction.atomic
def import_studlab_draft(draft_dir: Path) -> dict[str, int]:
    stats = {
        "faculties": 0,
        "training_centers": 0,
        "departments": 0,
        "laboratories": 0,
        "rooms": 0,
        "staff": 0,
    }
    lab_by_studlab_id: dict[str, Laboratory] = {}

    for row in _read_csv(draft_dir / "01_faculties.csv"):
        code = _clean(row, "faculty_code")
        if not code:
            continue
        _, created = Faculty.objects.update_or_create(
            code=code,
            defaults={
                "title": _clean(row, "faculty_title") or code,
                "ordering": int(_clean(row, "sort_order") or 0),
            },
        )
        if created:
            stats["faculties"] += 1

    for row in _read_csv(draft_dir / "02_training_centers.csv"):
        number_raw = _clean(row, "training_center_number")
        if not number_raw.isdigit():
            continue
        number = int(number_raw)
        _, created = TrainingCenter.objects.update_or_create(
            number=number,
            defaults={"name": _clean(row, "training_center_name")},
        )
        if created:
            stats["training_centers"] += 1

    faculty_by_code = {f.code: f for f in Faculty.objects.all()}

    for row in _read_csv(draft_dir / "03_departments.csv"):
        code = _clean(row, "department_code_suggested")
        title = _clean(row, "department_title")
        faculty_code = _clean(row, "faculty_code")
        if not code or not title:
            continue
        faculty = faculty_by_code.get(faculty_code)
        _, created = _upsert_department(code=code, title=title, faculty=faculty)
        if created:
            stats["departments"] += 1

    for row in _read_csv(draft_dir / "04_laboratories.csv"):
        studlab_id = _clean(row, "studlab_id")
        name = _clean(row, "lab_name_full") or _clean(row, "lab_name_short")
        if not studlab_id or not name:
            continue
        tc_numbers = [part for part in _clean(row, "training_center_numbers").split("|") if part.isdigit()]
        if not tc_numbers:
            continue
        training_center = TrainingCenter.objects.filter(number=int(tc_numbers[0])).first()
        if not training_center:
            continue
        faculty = faculty_by_code.get(_clean(row, "faculty_code"))
        laboratory, created = Laboratory.objects.update_or_create(
            training_center=training_center,
            name=_truncate(name, 256),
            defaults={
                "short_name": _truncate(_clean(row, "lab_name_short"), 64),
                "faculty": faculty,
                "lab_type": _lab_type(_clean(row, "lab_type")),
            },
        )
        lab_by_studlab_id[studlab_id] = laboratory
        if created:
            stats["laboratories"] += 1

        dept_code = _clean(row, "department_code_suggested")
        if dept_code:
            _upsert_department(
                code=dept_code,
                title=_clean(row, "department_title") or name,
                faculty=faculty,
            )

    for row in _read_csv(draft_dir / "05_rooms.csv"):
        room_number = _clean(row, "room_number")
        tc_raw = _clean(row, "training_center_number")
        if not room_number or not tc_raw.isdigit():
            continue
        training_center = TrainingCenter.objects.filter(number=int(tc_raw)).first()
        if not training_center:
            continue
        studlab_lab_id = _clean(row, "laboratory_studlab_id")
        laboratory = lab_by_studlab_id.get(studlab_lab_id)
        _, created = Room.objects.update_or_create(
            training_center=training_center,
            number=room_number,
            defaults={
                "name": _clean(row, "room_name_short") or _clean(row, "room_name"),
                "laboratory": laboratory,
            },
        )
        if created:
            stats["rooms"] += 1

    for row in _read_csv(draft_dir / "06_staff.csv"):
        email = _clean(row, "email").lower()
        if not email:
            continue
        role_raw = _clean(row, "role_suggested")
        role = UserRole.LAB_HEAD if role_raw == "LAB_HEAD" else UserRole.LAB_ADMIN
        user, created = User.objects.update_or_create(
            email=email,
            defaults={
                "first_name": _clean(row, "first_name"),
                "last_name": _clean(row, "last_name"),
                "role": role,
                "is_staff": True,
            },
        )
        studlab_lab_id = _clean(row, "laboratory_studlab_id")
        laboratory = lab_by_studlab_id.get(studlab_lab_id)
        tc_numbers = [part for part in _clean(row, "training_center_numbers").split("|") if part.isdigit()]
        training_center = (
            TrainingCenter.objects.filter(number=int(tc_numbers[0])).first() if tc_numbers else None
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.training_center = training_center
        profile.laboratory = laboratory
        profile.phone = _clean(row, "phone")[:32]
        profile.save(update_fields=["training_center", "laboratory", "phone"])
        if created:
            stats["staff"] += 1

    return stats
