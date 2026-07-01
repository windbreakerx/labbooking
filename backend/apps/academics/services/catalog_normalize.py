"""Normalization helpers for catalog import and deduplication."""

from __future__ import annotations

import re


def normalize_lab_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").replace("\n", " ")).strip().lower()
    text = text.replace("«", '"').replace("»", '"')
    text = re.sub(r"\s*([,.;:])\s*", r"\1", text)
    text = re.sub(r"[.,;]+$", "", text)
    return text


def lab_work_match_key(title: str, room_id: int | None) -> tuple[str, int | None]:
    return normalize_lab_title(title), room_id
