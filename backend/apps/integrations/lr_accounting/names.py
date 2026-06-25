"""Анонимизация ФИО студентов при импорте: перемешивание с учётом пола."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

Gender = str  # "male" | "female" | "unknown"

FALLBACK_MALE_PATRONYMICS = [
    "Петрович",
    "Сергеевич",
    "Андреевич",
    "Алексеевич",
    "Дмитриевич",
    "Иванович",
    "Николаевич",
    "Михайлович",
]
FALLBACK_FEMALE_PATRONYMICS = [
    "Петровна",
    "Сергеевна",
    "Андреевна",
    "Алексеевна",
    "Дмитриевна",
    "Ивановна",
    "Николаевна",
    "Михайловна",
]

MALE_FIRST_NAME_EXCEPTIONS = frozenset(
    {
        "никита",
        "илья",
        "кузьма",
        "фома",
        "лука",
        "савва",
        "миша",
        "саша",
        "женя",
        "валера",
        "паша",
    }
)
FEMALE_PATRONYMIC_SUFFIXES = ("овна", "евна", "ична", "вна")
MALE_PATRONYMIC_SUFFIXES = ("ович", "евич", "ич")


@dataclass(frozen=True)
class DisplayName:
    first_name: str
    last_name: str

    @property
    def full_first_name(self) -> str:
        return self.first_name


class StudentNameSource(Protocol):
    last_name: str
    first_name: str


def split_name_parts(student: StudentNameSource) -> tuple[str, str, str]:
    parts = student.first_name.split()
    first = parts[0] if parts else ""
    patronymic = parts[1] if len(parts) > 1 else ""
    return student.last_name.strip(), first.strip(), patronymic.strip()


def infer_gender(*, first: str, patronymic: str, last_name: str) -> Gender:
    if patronymic:
        lowered = patronymic.casefold()
        if lowered.endswith(FEMALE_PATRONYMIC_SUFFIXES):
            return "female"
        if lowered.endswith(MALE_PATRONYMIC_SUFFIXES):
            return "male"

    if last_name:
        if _looks_like_female_surname(last_name):
            return "female"
        if _looks_like_male_surname(last_name):
            return "male"

    if first:
        lowered = first.casefold()
        if lowered in MALE_FIRST_NAME_EXCEPTIONS:
            return "male"
        if _looks_like_female_first_name(first):
            return "female"
        if _looks_like_male_first_name(first):
            return "male"

    return "unknown"


def _looks_like_female_surname(last_name: str) -> bool:
    lowered = last_name.casefold()
    return lowered.endswith(("ова", "ева", "ина", "ына", "ая", "яя", "ска", "цка", "зая"))


def _looks_like_male_surname(last_name: str) -> bool:
    lowered = last_name.casefold()
    if _looks_like_female_surname(last_name):
        return False
    return lowered.endswith(("ов", "ев", "ин", "ын", "ий", "ой", "ский", "цкий", "ко", "юк", "ых"))


def _looks_like_female_first_name(first: str) -> bool:
    lowered = first.casefold()
    return lowered.endswith(("а", "я", "ия", "ь"))


def _looks_like_male_first_name(first: str) -> bool:
    lowered = first.casefold()
    return not _looks_like_female_first_name(first)


def feminize_last_name(last_name: str) -> str:
    if not last_name:
        return last_name
    if _looks_like_female_surname(last_name):
        return last_name
    if last_name.endswith("ский"):
        return last_name[:-4] + "ская"
    if last_name.endswith("цкий"):
        return last_name[:-4] + "цкая"
    if last_name.endswith("ой"):
        return last_name[:-2] + "ая"
    if last_name.endswith("ий"):
        return last_name[:-2] + "ая"
    if last_name.endswith(("ов", "ев", "ин", "ын")):
        return last_name + "а"
    return last_name


def masculinize_last_name(last_name: str) -> str:
    if not last_name:
        return last_name
    if _looks_like_male_surname(last_name):
        return last_name
    if last_name.endswith("ская"):
        return last_name[:-4] + "ский"
    if last_name.endswith("цкая"):
        return last_name[:-4] + "цкий"
    if last_name.endswith("ая") and not last_name.endswith(("овая", "евая")):
        return last_name[:-2] + "ой"
    if last_name.endswith("ова"):
        return last_name[:-1]
    if last_name.endswith("ева"):
        return last_name[:-1]
    if last_name.endswith("ина"):
        return last_name[:-1]
    if last_name.endswith("ына"):
        return last_name[:-1]
    return last_name


def normalize_last_name(last_name: str, gender: Gender) -> str:
    if gender == "female":
        return feminize_last_name(last_name)
    if gender == "male":
        return masculinize_last_name(last_name)
    return last_name


def _format_first_name(first: str, patronymic: str) -> str:
    if patronymic:
        return f"{first} {patronymic}"
    return first


def shuffle_student_display_names(
    students: list[StudentNameSource],
    *,
    seed: int | None = None,
) -> list[DisplayName]:
    """Перемешивает имена, фамилии и отчества между студентами внутри пола."""
    if not students:
        return []

    rng = random.Random(seed)
    genders: list[Gender] = []
    first_names: dict[Gender, list[str]] = {"male": [], "female": [], "unknown": []}
    patronymics: dict[Gender, list[str]] = {"male": [], "female": [], "unknown": []}
    last_names: dict[Gender, list[str]] = {"male": [], "female": [], "unknown": []}

    for student in students:
        last_name, first, patronymic = split_name_parts(student)
        gender = infer_gender(first=first, patronymic=patronymic, last_name=last_name)
        genders.append(gender)
        if first:
            first_names[gender].append(first)
        if patronymic:
            patronymics[gender].append(patronymic)
        if last_name:
            last_names[gender].append(normalize_last_name(last_name, gender))

    shuffled_first: dict[Gender, list[str]] = {}
    shuffled_patronymic: dict[Gender, list[str]] = {}
    shuffled_last: dict[Gender, list[str]] = {}
    gender_counts = {"male": 0, "female": 0, "unknown": 0}
    for gender in genders:
        gender_counts[gender] += 1
    for gender in ("male", "female", "unknown"):
        count = gender_counts[gender]
        shuffled_first[gender] = _shuffle_or_cycle(first_names[gender], count, rng)
        shuffled_patronymic[gender] = _shuffle_or_cycle(patronymics[gender], count, rng)
        shuffled_last[gender] = _shuffle_or_cycle(last_names[gender], count, rng)

    counters = {"male": 0, "female": 0, "unknown": 0}
    result: list[DisplayName] = []
    for gender in genders:
        index = counters[gender]
        counters[gender] += 1

        first = shuffled_first[gender][index] if shuffled_first[gender] else ""
        patronymic = shuffled_patronymic[gender][index] if shuffled_patronymic[gender] else ""
        last = shuffled_last[gender][index] if shuffled_last[gender] else ""

        if not patronymic:
            patronymic = _fallback_patronymic(gender, index)
        if not first:
            first = "Студент"
        if not last:
            last = "Анонимов" if gender != "female" else "Анонимова"

        result.append(
            DisplayName(
                first_name=_format_first_name(first, patronymic),
                last_name=last,
            )
        )

    return result


def _shuffle_or_cycle(values: list[str], minimum_size: int, rng: random.Random) -> list[str]:
    if not values:
        return []
    pool = values[:]
    rng.shuffle(pool)
    if len(pool) >= minimum_size:
        return pool
    expanded: list[str] = []
    while len(expanded) < minimum_size:
        chunk = pool[:]
        rng.shuffle(chunk)
        expanded.extend(chunk)
    return expanded[:minimum_size]


def _fallback_patronymic(gender: Gender, index: int) -> str:
    if gender == "female":
        return FALLBACK_FEMALE_PATRONYMICS[index % len(FALLBACK_FEMALE_PATRONYMICS)]
    return FALLBACK_MALE_PATRONYMICS[index % len(FALLBACK_MALE_PATRONYMICS)]
