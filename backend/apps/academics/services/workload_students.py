"""Generate synthetic student accounts from workload draft group sizes."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from django.db import transaction

from apps.academics.models import StudentGroup
from apps.academics.services.curated_catalog_import import KNOWN_DRAFTS
from apps.integrations.lr_accounting.students import allocate_student_id, new_year_counters, student_email
from apps.users.models import User, UserProfile, UserRole


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _clean(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _parse_count(value: str) -> int:
    if not value or not value.strip().isdigit():
        return 0
    return max(0, int(value.strip()))


def collect_group_targets(templates_dir: Path) -> dict[str, int]:
    targets: dict[str, int] = defaultdict(int)
    for draft_name in KNOWN_DRAFTS:
        groups_path = templates_dir / draft_name / "03_groups.csv"
        if not groups_path.is_file():
            continue
        for row in _read_csv(groups_path):
            group_name = _clean(row, "group_name")
            count = _parse_count(_clean(row, "student_count_suggested"))
            if group_name and count:
                targets[group_name] = max(targets[group_name], count)
    return dict(targets)


def _existing_student_count(group: StudentGroup) -> int:
    return User.objects.filter(role=UserRole.STUDENT, profile__student_group=group).count()


@transaction.atomic
def generate_workload_students(
    templates_dir: Path,
    *,
    default_password: str = "student123",
    skip_existing_groups: bool = True,
    email_domain: str = "stud.spmi.ru",
) -> dict[str, int]:
    stats = {"groups_processed": 0, "students_created": 0, "groups_skipped": 0}
    targets = collect_group_targets(templates_dir)
    year_counters = new_year_counters()

    for group_name in sorted(targets):
        target_count = targets[group_name]
        group = StudentGroup.objects.filter(name=group_name).first()
        if not group:
            continue

        existing = _existing_student_count(group)
        if skip_existing_groups and existing > 0:
            stats["groups_skipped"] += 1
            continue

        to_create = target_count - existing
        if to_create <= 0:
            continue

        stats["groups_processed"] += 1
        group_slug = re.sub(r"[^a-z0-9]+", "", group_name.lower()) or "group"

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
                },
            )
            user.set_password(default_password)
            user.save(update_fields=["password"])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.group_name = group_name
            profile.student_group = group
            profile.student_id = record_id
            profile.faculty = group.faculty
            profile.save(update_fields=["group_name", "student_group", "student_id", "faculty"])
            if created:
                stats["students_created"] += 1

    return stats
