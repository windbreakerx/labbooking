"""Generate synthetic student accounts from workload draft group sizes."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.academics.models import StudentGroup
from apps.academics.services.curated_catalog_import import KNOWN_DRAFTS
from apps.integrations.lr_accounting.students import allocate_student_id, new_year_counters, student_email
from apps.users.models import User, UserProfile, UserRole

logger = logging.getLogger(__name__)

DEFAULT_ACADEMIC_YEAR = "2025-2026"
DEFAULT_STUDENTS_PER_GROUP = 5
# Нормальная численность в Excel; значения вроде 285 — ошибка парсера/ячейки.
SANE_STUDENT_COUNT_MAX = 28


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _clean(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def normalize_student_count(
    count: int,
    *,
    max_per_group: int = SANE_STUDENT_COUNT_MAX,
) -> int:
    """Ограничить численность из Excel разумным диапазоном (16–28 в норме)."""
    if count <= 0:
        return 0
    return min(count, max_per_group)


def collect_group_targets(
    templates_dir: Path,
    *,
    academic_year: str | None = DEFAULT_ACADEMIC_YEAR,
    students_per_group: int = DEFAULT_STUDENTS_PER_GROUP,
) -> dict[str, int]:
    """Одна учебная группа (шифр) = одна когорта людей, независимо от года в CSV."""
    group_names: set[str] = set()
    for draft_name in KNOWN_DRAFTS:
        groups_path = templates_dir / draft_name / "03_groups.csv"
        if not groups_path.is_file():
            continue
        for row in _read_csv(groups_path):
            group_name = _clean(row, "group_name")
            source_sheets = _clean(row, "source_sheets")
            if academic_year and academic_year not in source_sheets:
                continue
            if group_name:
                group_names.add(group_name)
    return {name: students_per_group for name in sorted(group_names)}


def _existing_student_count(group: StudentGroup) -> int:
    return User.objects.filter(role=UserRole.STUDENT, profile__student_group=group).count()


def generate_workload_students(
    templates_dir: Path,
    *,
    default_password: str = "student123",
    skip_existing_groups: bool = True,
    email_domain: str = "stud.spmi.ru",
    academic_year: str | None = DEFAULT_ACADEMIC_YEAR,
    students_per_group: int = DEFAULT_STUDENTS_PER_GROUP,
) -> dict[str, int]:
    stats = {
        "groups_processed": 0,
        "students_created": 0,
        "groups_skipped": 0,
        "groups_missing": 0,
        "target_students": 0,
    }
    targets = collect_group_targets(
        templates_dir,
        academic_year=academic_year,
        students_per_group=students_per_group,
    )
    stats["target_students"] = sum(targets.values())
    year_counters = new_year_counters()
    password_hash = make_password(default_password)

    for group_name in sorted(targets):
        target_count = targets[group_name]
        group = StudentGroup.objects.filter(name=group_name).first()
        if not group:
            stats["groups_missing"] += 1
            continue

        existing = _existing_student_count(group)
        if skip_existing_groups and existing > 0:
            stats["groups_skipped"] += 1
            continue

        to_create = target_count - existing
        if to_create <= 0:
            continue

        stats["groups_processed"] += 1
        created_in_group = 0

        with transaction.atomic():
            for index in range(to_create):
                student_number = existing + index + 1
                try:
                    record_id = allocate_student_id(group_name, year_counters)
                except ValueError:
                    record_id = f"99{year_counters['99']:04d}"
                    year_counters["99"] += 1

                email = student_email(record_id)
                if email_domain != "stud.spmi.ru":
                    email = f"{email.split('@')[0]}@{email_domain}"

                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "first_name": f"Студент {student_number}",
                        "last_name": group_name,
                        "role": UserRole.STUDENT,
                        "is_staff": False,
                        "password": password_hash,
                    },
                )
                if created:
                    created_in_group += 1
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.group_name = group_name
                profile.student_group = group
                profile.student_id = record_id
                profile.faculty = group.faculty
                profile.save(update_fields=["group_name", "student_group", "student_id", "faculty"])

        stats["students_created"] += created_in_group
        logger.info(
            "workload students: %s +%s (target %s)",
            group_name,
            created_in_group,
            target_count,
        )

    return stats
