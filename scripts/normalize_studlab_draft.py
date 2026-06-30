#!/usr/bin/env python3
"""Normalize studlab draft CSV files for easier manual review."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import defaultdict
from pathlib import Path

FACULTY_ORDER = {
    "НГФ": 0,
    "ГФ": 1,
    "ГРФ": 2,
    "ФПМС": 3,
    "ММФ": 4,
    "СФ": 5,
    "ЭФ": 6,
    "ИБИО": 7,
}

LAB_TYPE_RU = {
    "COMPLEX": "Комплексная",
    "REGULAR": "Кафедральная",
    "INTERDEPT": "Межкафедральная",
}

NGF_DEPARTMENT_RULES: list[tuple[list[str], str, str]] = [
    (
        [
            "газораспредел",
            "газопотреблен",
            "газонефтепровод",
            "газонефтехранилищ",
            "компрессор",
            "транспортировк",
            "газогенератор",
            "трубопровод",
        ],
        "ТНГ",
        "Кафедра транспорта и хранения нефти и газа",
    ),
    (
        [
            "бурен",
            "бурового",
            "тампонаж",
            "глинист",
            "капитальн",
            "ремонт скважин",
            "породоразруша",
        ],
        "БУР",
        "Кафедра бурения скважин",
    ),
    (
        [
            "разработк",
            "месторожд",
            "гидродинам",
            "эксплуатации нефтяных",
            "визуализац",
            "нефтегазопромысл",
        ],
        "РНГМ",
        "Кафедра разработки и эксплуатации нефтяных и газовых месторождений",
    ),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_department_title(hint: str) -> str:
    hint = (hint or "").strip()
    if not hint:
        return ""
    if hint.lower().startswith("кафедра "):
        return hint
    return f"Кафедра {hint}"


def suggest_ngf_department(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for keywords, code, title in NGF_DEPARTMENT_RULES:
        if any(keyword in lowered for keyword in keywords):
            return code, title
    return "", ""


def split_full_name(full_name: str) -> tuple[str, str, str]:
    parts = [part for part in re.split(r"\s+", full_name.strip()) if part]
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], ""
    if len(parts) == 1:
        return parts[0], "", ""
    return "", "", ""


def normalize_phone(phone: str) -> tuple[str, str]:
    phone = (phone or "").strip()
    if not phone or phone == "—":
        return "", ""
    internal = ""
    match = re.search(r"\((\d{2,4}-\d{2,4}|\d{2,4})\)\s*$", phone)
    if match:
        internal = match.group(1)
        phone = phone[: match.start()].strip().rstrip(",").strip()
    return phone, internal


def room_sort_key(room_number: str) -> tuple[int, str]:
    digits = re.sub(r"\D", "", room_number)
    return (int(digits) if digits else 999999, room_number)


def short_lab_name(name: str, faculty_code: str = "", max_len: int = 72) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip())
    prefixes = (
        "Комплексная учебная лаборатория ",
        "Учебно-научная лаборатория ",
        "Учебная лаборатория кафедры ",
        "Учебная лаборатория ",
        "Межкафедральная учебно-научная лаборатория ",
        "Межкафедральная лаборатория ",
        "Многофункциональная учебная лаборатория ",
    )
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    cleaned = cleaned.strip(" \"'«»")
    if re.fullmatch(r".*факультета", cleaned, flags=re.IGNORECASE) and faculty_code:
        return f"КУЛ {faculty_code}"
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def truncate(text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def backup_raw(source_dir: Path, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for path in source_dir.glob("studlab_*.csv"):
        target = raw_dir / path.name
        if not target.exists():
            shutil.copy2(path, target)


def normalize_faculties(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        code = row.get("code", "").strip()
        normalized.append(
            {
                "faculty_code": code,
                "faculty_title": row.get("title", "").strip(),
                "sort_order": str(FACULTY_ORDER.get(code, 99)),
                "check_ok": "",
                "review_comment": "",
            }
        )
    normalized.sort(key=lambda item: int(item["sort_order"]))
    return normalized


def normalize_training_centers(
    rows: list[dict[str, str]],
    laboratories: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_number: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"faculty_codes": set(), "faculty_titles": set()})
    for row in rows:
        number = row.get("number", "").strip()
        if not number:
            continue
        by_number[number]["faculty_codes"].add(row.get("faculty_code", "").strip())
        by_number[number]["faculty_titles"].add(row.get("faculty_title", "").strip())
    for lab in laboratories:
        for number in lab.get("training_center_numbers", "").split("|"):
            number = number.strip()
            if not number:
                continue
            by_number[number]["faculty_codes"].add(lab.get("faculty_code", "").strip())
            by_number[number]["faculty_titles"].add(lab.get("faculty_title", "").strip())

    normalized = []
    for number in sorted(by_number, key=lambda value: int(value)):
        payload = by_number[number]
        normalized.append(
            {
                "training_center_number": number,
                "training_center_name": f"Учебный центр №{number}",
                "faculty_codes": "|".join(sorted(code for code in payload["faculty_codes"] if code)),
                "faculty_titles": "|".join(sorted(title for title in payload["faculty_titles"] if title)),
                "check_ok": "",
                "review_comment": "",
            }
        )
    return normalized


def normalize_laboratories(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        faculty_code = row.get("faculty_code", "").strip()
        department_title = normalize_department_title(row.get("department_hint", ""))
        department_code = ""
        if faculty_code == "НГФ" and not department_title:
            department_code, department_title = suggest_ngf_department(row.get("name", ""))
        head_last, head_first, head_middle = split_full_name(row.get("head_full_name", ""))
        phone, internal = normalize_phone(row.get("head_phone", ""))
        lab_type = row.get("lab_type", "").strip()
        normalized.append(
            {
                "faculty_code": faculty_code,
                "faculty_title": row.get("faculty_title", "").strip(),
                "studlab_id": row.get("studlab_id", "").strip(),
                "lab_name_short": short_lab_name(row.get("name", ""), faculty_code),
                "lab_name_full": row.get("name", "").strip(),
                "department_title": department_title,
                "department_code_suggested": department_code,
                "lab_type": lab_type,
                "lab_type_ru": LAB_TYPE_RU.get(lab_type, lab_type),
                "training_center_numbers": row.get("training_center_numbers", "").strip(),
                "head_last_name": head_last,
                "head_first_name": head_first,
                "head_middle_name": head_middle,
                "head_position": row.get("head_position", "").strip(),
                "head_email": row.get("head_email", "").strip() or row.get("lab_email", "").strip(),
                "head_phone": phone,
                "head_internal_phone": internal,
                "head_room": row.get("head_room", "").strip(),
                "staff_count": row.get("staff_count", "").strip(),
                "rooms_count": row.get("rooms_count", "").strip(),
                "studlab_url": row.get("source_url", "").strip(),
                "check_ok": "",
                "review_comment": "",
            }
        )
    normalized.sort(
        key=lambda item: (
            FACULTY_ORDER.get(item["faculty_code"], 99),
            int(item["studlab_id"]) if item["studlab_id"].isdigit() else 999,
        )
    )
    return normalized


def normalize_rooms(rows: list[dict[str, str]], laboratories: list[dict[str, str]]) -> list[dict[str, str]]:
    lab_by_id = {lab["studlab_id"]: lab for lab in laboratories}
    normalized = []
    for row in rows:
        faculty_code = row.get("faculty_code", "").strip()
        lab_id = row.get("laboratory_studlab_id", "").strip()
        lab = lab_by_id.get(lab_id, {})
        department_title = normalize_department_title(row.get("department_hint", "") or lab.get("department_title", ""))
        department_code = lab.get("department_code_suggested", "")
        room_name = row.get("room_name", "").strip()
        if faculty_code == "НГФ" and not department_title:
            department_code, department_title = suggest_ngf_department(room_name)
        normalized.append(
            {
                "faculty_code": faculty_code,
                "training_center_number": row.get("training_center_number", "").strip(),
                "room_number": row.get("room_number", "").strip(),
                "room_name": room_name,
                "room_name_short": short_lab_name(room_name, max_len=64),
                "laboratory_studlab_id": lab_id,
                "laboratory_name_short": lab.get("lab_name_short", short_lab_name(row.get("laboratory_name", ""))),
                "department_code_suggested": department_code,
                "department_title": department_title,
                "purpose_short": truncate(row.get("purpose", "")),
                "studlab_url": row.get("source_url", "").strip(),
                "check_ok": "",
                "review_comment": "",
            }
        )
    normalized.sort(
        key=lambda item: (
            FACULTY_ORDER.get(item["faculty_code"], 99),
            int(item["training_center_number"]) if item["training_center_number"].isdigit() else 99,
            room_sort_key(item["room_number"]),
        )
    )
    return normalized


def normalize_staff(rows: list[dict[str, str]], laboratories: list[dict[str, str]]) -> list[dict[str, str]]:
    lab_by_id = {lab["studlab_id"]: lab for lab in laboratories}
    normalized = []
    for row in rows:
        faculty_code = row.get("faculty_code", "").strip()
        lab_id = row.get("laboratory_studlab_id", "").strip()
        lab = lab_by_id.get(lab_id, {})
        phone, internal = normalize_phone(row.get("phone", ""))
        is_head = row.get("is_head", "").strip() in {"1", "true", "True", "yes"}
        normalized.append(
            {
                "faculty_code": faculty_code,
                "laboratory_studlab_id": lab_id,
                "laboratory_name_short": lab.get("lab_name_short", short_lab_name(row.get("laboratory_name", ""))),
                "department_title": lab.get("department_title", ""),
                "last_name": row.get("last_name", "").strip(),
                "first_name": row.get("first_name", "").strip(),
                "middle_name": row.get("middle_name", "").strip(),
                "full_name": " ".join(
                    part
                    for part in [
                        row.get("last_name", "").strip(),
                        row.get("first_name", "").strip(),
                        row.get("middle_name", "").strip(),
                    ]
                    if part
                ),
                "position": row.get("position", "").strip(),
                "email": row.get("email", "").strip(),
                "phone": phone,
                "internal_phone": internal,
                "room_number": row.get("room_number", "").strip(),
                "training_center_numbers": row.get("training_center_numbers", "").strip(),
                "is_head": "да" if is_head else "нет",
                "role_suggested": "LAB_HEAD" if is_head else "LAB_ADMIN",
                "studlab_url": row.get("source_url", "").strip(),
                "check_ok": "",
                "review_comment": "",
            }
        )
    normalized.sort(
        key=lambda item: (
            FACULTY_ORDER.get(item["faculty_code"], 99),
            int(item["laboratory_studlab_id"]) if item["laboratory_studlab_id"].isdigit() else 999,
            0 if item["is_head"] == "да" else 1,
            item["last_name"],
            item["first_name"],
        )
    )
    return normalized


def build_departments(laboratories: list[dict[str, str]], rooms: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for source_rows in (laboratories, rooms):
        for row in source_rows:
            title = row.get("department_title", "").strip()
            code = row.get("department_code_suggested", "").strip()
            faculty_code = row.get("faculty_code", "").strip()
            if not title:
                continue
            key = (faculty_code, title)
            if key not in seen:
                seen[key] = {
                    "faculty_code": faculty_code,
                    "department_code_suggested": code,
                    "department_title": title,
                    "source": "studlab_hint",
                    "check_ok": "",
                    "review_comment": "",
                }
            elif code and not seen[key]["department_code_suggested"]:
                seen[key]["department_code_suggested"] = code
    rows = list(seen.values())
    rows.sort(key=lambda item: (FACULTY_ORDER.get(item["faculty_code"], 99), item["department_title"]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize studlab draft CSV files.")
    parser.add_argument(
        "--input",
        default="docs/csv_templates/studlab_draft",
        help="Directory with raw studlab_*.csv files",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output directory (defaults to --input)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output or args.input)
    raw_dir = input_dir / "_raw"

    required = [
        "studlab_faculties.csv",
        "studlab_training_centers.csv",
        "studlab_laboratories.csv",
        "studlab_rooms.csv",
        "studlab_staff.csv",
    ]
    for name in required:
        if not (input_dir / name).exists():
            raise SystemExit(f"Missing file: {input_dir / name}")

    backup_raw(input_dir, raw_dir)

    faculties = normalize_faculties(read_csv(input_dir / "studlab_faculties.csv"))
    laboratories_raw = read_csv(input_dir / "studlab_laboratories.csv")
    laboratories = normalize_laboratories(laboratories_raw)
    training_centers = normalize_training_centers(
        read_csv(input_dir / "studlab_training_centers.csv"),
        laboratories_raw,
    )
    rooms = normalize_rooms(read_csv(input_dir / "studlab_rooms.csv"), laboratories)
    staff = normalize_staff(read_csv(input_dir / "studlab_staff.csv"), laboratories)
    departments = build_departments(laboratories, rooms)

    write_csv(
        output_dir / "01_faculties.csv",
        ["faculty_code", "faculty_title", "sort_order", "check_ok", "review_comment"],
        faculties,
    )
    write_csv(
        output_dir / "02_training_centers.csv",
        [
            "training_center_number",
            "training_center_name",
            "faculty_codes",
            "faculty_titles",
            "check_ok",
            "review_comment",
        ],
        training_centers,
    )
    write_csv(
        output_dir / "03_departments.csv",
        [
            "faculty_code",
            "department_code_suggested",
            "department_title",
            "source",
            "check_ok",
            "review_comment",
        ],
        departments,
    )
    write_csv(
        output_dir / "04_laboratories.csv",
        [
            "faculty_code",
            "faculty_title",
            "studlab_id",
            "lab_name_short",
            "lab_name_full",
            "department_title",
            "department_code_suggested",
            "lab_type",
            "lab_type_ru",
            "training_center_numbers",
            "head_last_name",
            "head_first_name",
            "head_middle_name",
            "head_position",
            "head_email",
            "head_phone",
            "head_internal_phone",
            "head_room",
            "staff_count",
            "rooms_count",
            "studlab_url",
            "check_ok",
            "review_comment",
        ],
        laboratories,
    )
    write_csv(
        output_dir / "05_rooms.csv",
        [
            "faculty_code",
            "training_center_number",
            "room_number",
            "room_name_short",
            "room_name",
            "laboratory_studlab_id",
            "laboratory_name_short",
            "department_code_suggested",
            "department_title",
            "purpose_short",
            "studlab_url",
            "check_ok",
            "review_comment",
        ],
        rooms,
    )
    write_csv(
        output_dir / "06_staff.csv",
        [
            "faculty_code",
            "laboratory_studlab_id",
            "laboratory_name_short",
            "department_title",
            "full_name",
            "last_name",
            "first_name",
            "middle_name",
            "position",
            "email",
            "phone",
            "internal_phone",
            "room_number",
            "training_center_numbers",
            "is_head",
            "role_suggested",
            "studlab_url",
            "check_ok",
            "review_comment",
        ],
        staff,
    )

    readme = output_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Studlab draft (normalized)",
                "",
                "Нормализованные таблицы для ручной проверки. Исходный дамп парсера — в `_raw/`.",
                "",
                "## Порядок проверки",
                "",
                "1. `01_faculties.csv` — справочник факультетов",
                "2. `02_training_centers.csv` — УЦ (дедуп по номеру)",
                "3. `03_departments.csv` — кафедры, собранные из подсказок",
                "4. `04_laboratories.csv` — лаборатории",
                "5. `05_rooms.csv` — аудитории (сортировка: факультет → УЦ → номер)",
                "6. `06_staff.csv` — сотрудники (руководитель первым в группе лаборатории)",
                "",
                "## Колонки для ревью",
                "",
                "- `check_ok` — поставьте `1` / `да`, когда строка проверена",
                "- `review_comment` — замечания и правки",
                "",
                "## Эвристики (проверить вручную)",
                "",
                "- `department_code_suggested` для НГФ — по ключевым словам в названии аудитории",
                "- `role_suggested` — LAB_HEAD / LAB_ADMIN",
                "- `phone` и `internal_phone` разделены из строки вида `8 (812) ... (14-83)`",
                "",
                "## Перегенерация",
                "",
                "```bash",
                "python scripts/scrape_studlab.py",
                "python scripts/normalize_studlab_draft.py",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Normalized files written to: {output_dir.resolve()}")
    print(f"Raw backup: {raw_dir.resolve()}")
    print(
        f"Counts: faculties={len(faculties)}, training_centers={len(training_centers)}, "
        f"departments={len(departments)}, laboratories={len(laboratories)}, "
        f"rooms={len(rooms)}, staff={len(staff)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
