"""Генерация номера зачётки и email студента для импорта из Excel."""

from __future__ import annotations

import re
from collections import defaultdict

STUDENT_EMAIL_DOMAIN = "stud.spmi.ru"


def admission_year_from_group(group_name: str) -> str:
    cleaned = group_name.strip()
    match = re.search(r"-(\d{2})(?:-\d+)?$", cleaned)
    if match:
        return match.group(1)
    match = re.search(r"(\d{2})$", cleaned)
    if match:
        return match.group(1)
    raise ValueError(f"Не удалось определить год поступления для группы {group_name!r}")


def allocate_student_id(group_name: str, counters: dict[str, int]) -> str:
    year = admission_year_from_group(group_name)
    counters[year] += 1
    return f"{year}{counters[year]:04d}"


def student_email(student_id: str) -> str:
    digits = re.sub(r"\D", "", student_id)
    if not digits:
        raise ValueError(f"Некорректный номер зачётки: {student_id!r}")
    return f"s{digits}@{STUDENT_EMAIL_DOMAIN}"


def new_year_counters() -> dict[str, int]:
    return defaultdict(int)
