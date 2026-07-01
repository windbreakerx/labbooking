"""Normalization helpers for catalog import and deduplication."""

from __future__ import annotations

import re

from apps.academics.models import ALLOWED_LAB_DURATIONS


def normalize_lab_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").replace("\n", " ")).strip().lower()
    text = text.replace("«", '"').replace("»", '"')
    text = re.sub(r"\s*([,.;:])\s*", r"\1", text)
    text = re.sub(r"[.,;]+$", "", text)
    return text


def truncate_field(value: str, max_length: int) -> str:
    text = (value or "").strip()
    return text[:max_length] if text else text


def lab_work_match_key(title: str, room_id: int | None) -> tuple[str, int | None]:
    return normalize_lab_title(title), room_id


def normalize_lab_duration(
    minutes: int | None,
    *,
    allowed: tuple[int, ...] = ALLOWED_LAB_DURATIONS,
    default: int | None = None,
) -> int | None:
    """Округлить длительность вверх до ближайшего допустимого значения (20→30, 39→45, …)."""
    if minutes is None:
        return default
    if minutes <= 0:
        return default
    if minutes in allowed:
        return minutes
    for value in allowed:
        if value >= minutes:
            return value
    return allowed[-1]
