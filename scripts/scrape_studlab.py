#!/usr/bin/env python3
"""Scrape studlab.spmi.ru into draft CSV files for manual review.

Usage:
    python scripts/scrape_studlab.py
    python scripts/scrape_studlab.py --faculty neftegaz
    python scripts/scrape_studlab.py --output docs/csv_templates/studlab_draft
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://studlab.spmi.ru"
USER_AGENT = "labbooking-scraper/1.0 (+internal draft import)"

FACULTY_CODES = {
    "Нефтегазовый факультет": "НГФ",
    "Горный факультет": "ГФ",
    "Геологоразведочный факультет": "ГРФ",
    "Факультет переработки минерального сырья": "ФПМС",
    "Механико-машиностроительный факультет": "ММФ",
    "Строительный факультет": "СФ",
    "Энергетический факультет": "ЭФ",
    "Институт базового инженерного образования": "ИБИО",
}

FACULTY_ALIASES = {
    "neftegaz": "Нефтегазовый факультет",
    "ngf": "Нефтегазовый факультет",
}

TAXONOMY_FEEDS = {
    1: "Факультет переработки минерального сырья",
    2: "Нефтегазовый факультет",
    3: "Геологоразведочный факультет",
    4: "Горный факультет",
    5: "Механико-машиностроительный факультет",
    6: "Строительный факультет",
    7: "Энергетический факультет",
    8: "Институт базового инженерного образования",
}

ROOM_TITLE_RE = re.compile(
    r"Аудитория\s*№\s*(\S+)\s*\(УЦ\s*№\s*(\d+)\)\s*[-–—]\s*(.+)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:тел\.?|телефон)\s*:?\s*([^<\n]+)", re.IGNORECASE)
DEPARTMENT_RE = re.compile(
    r"кафедр[аы]\s+([^\"«»\n<]+?)(?:\s*[\"»]|$|\s+с\s+использованием)",
    re.IGNORECASE,
)


@dataclass
class StaffMember:
    last_name: str
    first_name: str
    middle_name: str
    position: str
    email: str
    phone: str
    is_head: bool
    head_room: str = ""


@dataclass
class RoomRecord:
    training_center_number: int
    room_number: str
    room_name: str
    purpose: str = ""


@dataclass
class LaboratoryRecord:
    studlab_id: str
    name: str
    faculty_title: str
    faculty_code: str
    department_hint: str
    lab_type: str
    training_center_number: str
    head: StaffMember | None
    lab_email: str
    lab_phone: str
    head_room: str
    staff: list[StaffMember] = field(default_factory=list)
    rooms: list[RoomRecord] = field(default_factory=list)
    source_url: str = ""


def fetch(url: str, delay: float) -> str:
    time.sleep(delay)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc


def faculty_code(title: str) -> str:
    return FACULTY_CODES.get(title.strip(), "")


def infer_lab_type(name: str, description: str = "") -> str:
    text = f"{name} {description}".lower()
    if "комплексн" in text:
        return "COMPLEX"
    if "межкафедр" in text:
        return "INTERDEPT"
    if "кафедр" in text:
        return "REGULAR"
    return "REGULAR"


def infer_department(name: str, description: str = "") -> str:
    for source in (name, description):
        match = DEPARTMENT_RE.search(source)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .\"'«»")
    return ""


def split_fio(full_name: str) -> tuple[str, str, str]:
    cleaned = re.sub(r"<br\s*/?>", " ", full_name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", unescape(cleaned)).strip()
    parts = cleaned.split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def clean_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_block(html: str, class_name: str) -> list[str]:
    pattern = re.compile(
        rf'<div class="{re.escape(class_name)}">(.*?)</div>\s*</div>\s*</div>\s*</div>',
        re.IGNORECASE | re.DOTALL,
    )
    return [block.strip() for block in pattern.findall(html)]


def parse_staff_info(block: str) -> StaffMember | None:
    name_match = re.search(r'class="has-text-weight-bold"[^>]*>([^<]+)<', block)
    if not name_match:
        return None
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", block, re.IGNORECASE | re.DOTALL)
    position = ""
    email = ""
    phone = ""
    for paragraph in paragraphs[1:]:
        text = clean_text(paragraph)
        if not text:
            continue
        lower = text.lower()
        if lower.startswith("e-mail:") or lower.startswith("email:"):
            email_match = EMAIL_RE.search(text)
            email = email_match.group(0) if email_match else text.split(":", 1)[-1].strip()
        elif lower.startswith("тел"):
            phone = text.split(":", 1)[-1].strip()
        elif not position:
            position = text
    last_name, first_name, middle_name = split_fio(name_match.group(1))
    return StaffMember(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        position=position,
        email=email,
        phone=phone,
        is_head=False,
    )


def parse_head(html: str) -> tuple[StaffMember | None, str, str, str]:
    position_match = re.search(r'class="person-card-position"[^>]*>(.*?)</h5>', html, re.S)
    fio_match = re.search(r'class="person-card-fio"[^>]*>(.*?)</h5>', html, re.S)
    value_match = re.search(
        r'class="column person-card-value-column">\s*(.*?)\s*</div>\s*</div>\s*</div>\s*</div>\s*</div>',
        html,
        re.S,
    )
    if not fio_match:
        return None, "", "", ""
    position = clean_text(position_match.group(1)) if position_match else ""
    value_text = value_match.group(1) if value_match else ""
    bold_values = [clean_text(match) for match in re.findall(r"<p[^>]*>(.*?)</p>", value_text, re.S)]
    bold_values = [value for value in bold_values if value]
    room = bold_values[0] if len(bold_values) > 0 else ""
    phone = bold_values[1] if len(bold_values) > 1 else ""
    email = bold_values[2] if len(bold_values) > 2 else ""
    if not email:
        email_match = EMAIL_RE.search(value_text)
        email = email_match.group(0) if email_match else ""
    if not email:
        contact_match = re.search(
            r'class="contact-item-title">Почта</div>\s*<div class="contact-item-info">([^<]+)',
            html,
            re.S,
        )
        if contact_match:
            email = clean_text(contact_match.group(1))
    last_name, first_name, middle_name = split_fio(fio_match.group(1))
    head = StaffMember(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        position=position,
        email=email,
        phone=phone,
        is_head=True,
        head_room=room,
    )
    return head, room, phone, email


def parse_rooms(html: str) -> list[RoomRecord]:
    rooms: list[RoomRecord] = []
    for block in re.findall(r'<div class="lab-room-card">(.*?)</div>\s*</div>\s*</div>', html, re.S):
        title_match = re.search(r'class="has-text-weight-bold mb-2"[^>]*>([^<]+)<', block)
        if not title_match:
            continue
        title = clean_text(title_match.group(1))
        room_match = ROOM_TITLE_RE.match(title)
        if not room_match:
            continue
        purpose = ""
        purpose_match = re.search(
            r"Назначение лаборатории:</p>\s*<p>(.*?)</p>",
            block,
            re.IGNORECASE | re.DOTALL,
        )
        if purpose_match:
            purpose = clean_text(purpose_match.group(1))
        rooms.append(
            RoomRecord(
                training_center_number=int(room_match.group(2)),
                room_number=room_match.group(1),
                room_name=room_match.group(3).strip(),
                purpose=purpose,
            )
        )
    return rooms


def parse_lab_page(html: str, studlab_id: str, faculty_title: str, lab_name: str) -> LaboratoryRecord:
    description_match = re.search(r'<div class="lab-description[^"]*">(.*?)</div>', html, re.S)
    description = clean_text(description_match.group(1)) if description_match else ""
    head, head_room, lab_phone, lab_email = parse_head(html)
    staff = [member for block in extract_block(html, "staff-info") if (member := parse_staff_info(block))]
    rooms = parse_rooms(html)
    tc_numbers = sorted({room.training_center_number for room in rooms})
    if head and head_room and not head.head_room:
        head.head_room = head_room
    return LaboratoryRecord(
        studlab_id=studlab_id,
        name=lab_name or clean_text(re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S).group(1)),
        faculty_title=faculty_title,
        faculty_code=faculty_code(faculty_title),
        department_hint=infer_department(lab_name, description),
        lab_type=infer_lab_type(lab_name, description),
        training_center_number="|".join(str(number) for number in tc_numbers) or "",
        head=head,
        lab_email=lab_email,
        lab_phone=lab_phone,
        head_room=head_room,
        staff=staff,
        rooms=rooms,
        source_url=f"{BASE_URL}/{studlab_id}",
    )


class HomePageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.faculty_labs: dict[str, list[tuple[str, str]]] = {}
        self._current_faculty = ""
        self._capture_faculty = False
        self._capture_lab = False
        self._lab_href = ""
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_value = attrs_dict.get("class", "")
        if tag == "div" and "faculty-title" in class_value:
            self._capture_faculty = True
            self._text_chunks = []
        if tag == "a" and self._current_faculty and attrs_dict.get("href", "").startswith("/"):
            href = attrs_dict["href"].strip("/")
            if href.isdigit():
                self._capture_lab = True
                self._lab_href = href
                self._text_chunks = []
        if tag == "p" and (self._capture_faculty or self._capture_lab):
            self._text_chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture_faculty or self._capture_lab:
            text = data.strip()
            if text:
                self._text_chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._capture_faculty:
            faculty = " ".join(self._text_chunks).strip()
            if faculty:
                self._current_faculty = faculty
                self.faculty_labs.setdefault(faculty, [])
            self._capture_faculty = False
            self._text_chunks = []
        if tag == "a" and self._capture_lab:
            lab_name = " ".join(self._text_chunks).strip()
            if lab_name and self._current_faculty:
                self.faculty_labs.setdefault(self._current_faculty, []).append((self._lab_href, lab_name))
            self._capture_lab = False
            self._lab_href = ""
            self._text_chunks = []


def parse_homepage(html: str) -> dict[str, list[tuple[str, str]]]:
    parser = HomePageParser()
    parser.feed(html)
    return parser.faculty_labs


def discover_labs(html: str, faculty_filter: str | None = None) -> list[tuple[str, str, str]]:
    mapping = parse_homepage(html)
    labs: list[tuple[str, str, str]] = []
    for faculty_title, entries in mapping.items():
        if faculty_filter and faculty_title != faculty_filter:
            continue
        for studlab_id, lab_name in entries:
            labs.append((studlab_id, faculty_title, lab_name))
    return labs


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_rows(labs: list[LaboratoryRecord]) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    faculties: dict[str, dict[str, str]] = {}
    training_centers: dict[tuple[int, str], dict[str, str]] = {}
    laboratory_rows: list[dict[str, str]] = []
    room_rows: list[dict[str, str]] = []
    staff_rows: list[dict[str, str]] = []
    seen_staff: set[tuple[str, str]] = set()

    for lab in labs:
        if lab.faculty_title and lab.faculty_title not in faculties:
            faculties[lab.faculty_title] = {
                "code": lab.faculty_code,
                "title": lab.faculty_title,
                "source": "studlab.spmi.ru",
            }
        laboratory_rows.append(
            {
                "studlab_id": lab.studlab_id,
                "name": lab.name,
                "faculty_code": lab.faculty_code,
                "faculty_title": lab.faculty_title,
                "department_hint": lab.department_hint,
                "lab_type": lab.lab_type,
                "training_center_numbers": lab.training_center_number,
                "head_full_name": " ".join(
                    part for part in [lab.head.last_name, lab.head.first_name, lab.head.middle_name] if part
                )
                if lab.head
                else "",
                "head_position": lab.head.position if lab.head else "",
                "head_email": lab.head.email if lab.head else lab.lab_email,
                "head_phone": lab.head.phone if lab.head else lab.lab_phone,
                "head_room": lab.head_room,
                "lab_email": lab.lab_email,
                "staff_count": str(len(lab.staff) + (1 if lab.head else 0)),
                "rooms_count": str(len(lab.rooms)),
                "source_url": lab.source_url,
                "notes": "draft from studlab; verify department_hint and training centers manually",
            }
        )
        for room in lab.rooms:
            key = (room.training_center_number, lab.faculty_code)
            if key not in training_centers:
                training_centers[key] = {
                    "number": str(room.training_center_number),
                    "name": f"Учебный центр №{room.training_center_number}",
                    "faculty_code": lab.faculty_code,
                    "faculty_title": lab.faculty_title,
                    "source": "studlab.spmi.ru",
                }
            room_rows.append(
                {
                    "training_center_number": str(room.training_center_number),
                    "room_number": room.room_number,
                    "room_name": room.room_name,
                    "laboratory_studlab_id": lab.studlab_id,
                    "laboratory_name": lab.name,
                    "faculty_code": lab.faculty_code,
                    "faculty_title": lab.faculty_title,
                    "department_hint": lab.department_hint,
                    "purpose": room.purpose,
                    "source_url": lab.source_url,
                    "notes": "draft from studlab",
                }
            )
        members = ([lab.head] if lab.head else []) + lab.staff
        for member in members:
            if not member:
                continue
            dedupe_key = (member.email.lower(), lab.studlab_id) if member.email else (
                member.last_name,
                member.first_name,
                lab.studlab_id,
            )
            if dedupe_key in seen_staff:
                continue
            seen_staff.add(dedupe_key)
            staff_rows.append(
                {
                    "email": member.email,
                    "last_name": member.last_name,
                    "first_name": member.first_name,
                    "middle_name": member.middle_name,
                    "position": member.position,
                    "phone": member.phone,
                    "is_head": "1" if member.is_head else "0",
                    "laboratory_studlab_id": lab.studlab_id,
                    "laboratory_name": lab.name,
                    "faculty_code": lab.faculty_code,
                    "faculty_title": lab.faculty_title,
                    "training_center_numbers": lab.training_center_number,
                    "room_number": member.head_room,
                    "role_suggestion": "LAB_HEAD" if member.is_head else "LAB_ADMIN",
                    "source_url": lab.source_url,
                    "notes": "map to pilot_staff.csv after manual review; role_suggestion is heuristic",
                }
            )
    return (
        list(faculties.values()),
        list(training_centers.values()),
        laboratory_rows,
        room_rows,
        staff_rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape studlab.spmi.ru into draft CSV files.")
    parser.add_argument(
        "--output",
        default="docs/csv_templates/studlab_draft",
        help="Output directory for CSV files",
    )
    parser.add_argument(
        "--faculty",
        default="",
        help="Limit to one faculty title or alias (e.g. neftegaz)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Delay between HTTP requests in seconds",
    )
    args = parser.parse_args()

    faculty_filter = args.faculty.strip()
    if faculty_filter in FACULTY_ALIASES:
        faculty_filter = FACULTY_ALIASES[faculty_filter]

    output_dir = Path(args.output)
    home_html = fetch(f"{BASE_URL}/", args.delay)
    lab_index = discover_labs(home_html, faculty_filter or None)
    if not lab_index:
        print("No laboratories discovered.", file=sys.stderr)
        return 1

    parsed_labs: list[LaboratoryRecord] = []
    for studlab_id, faculty_title, lab_name in lab_index:
        print(f"Fetching /{studlab_id}: {lab_name}")
        lab_html = fetch(f"{BASE_URL}/{studlab_id}", args.delay)
        parsed_labs.append(parse_lab_page(lab_html, studlab_id, faculty_title, lab_name))

    faculties, training_centers, laboratories, rooms, staff = build_rows(parsed_labs)

    write_csv(
        output_dir / "studlab_faculties.csv",
        ["code", "title", "source"],
        faculties,
    )
    write_csv(
        output_dir / "studlab_training_centers.csv",
        ["number", "name", "faculty_code", "faculty_title", "source"],
        training_centers,
    )
    write_csv(
        output_dir / "studlab_laboratories.csv",
        [
            "studlab_id",
            "name",
            "faculty_code",
            "faculty_title",
            "department_hint",
            "lab_type",
            "training_center_numbers",
            "head_full_name",
            "head_position",
            "head_email",
            "head_phone",
            "head_room",
            "lab_email",
            "staff_count",
            "rooms_count",
            "source_url",
            "notes",
        ],
        laboratories,
    )
    write_csv(
        output_dir / "studlab_rooms.csv",
        [
            "training_center_number",
            "room_number",
            "room_name",
            "laboratory_studlab_id",
            "laboratory_name",
            "faculty_code",
            "faculty_title",
            "department_hint",
            "purpose",
            "source_url",
            "notes",
        ],
        rooms,
    )
    write_csv(
        output_dir / "studlab_staff.csv",
        [
            "email",
            "last_name",
            "first_name",
            "middle_name",
            "position",
            "phone",
            "is_head",
            "laboratory_studlab_id",
            "laboratory_name",
            "faculty_code",
            "faculty_title",
            "training_center_numbers",
            "room_number",
            "role_suggestion",
            "source_url",
            "notes",
        ],
        staff,
    )

    readme = output_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Draft CSV from studlab.spmi.ru",
                "",
                "Сгенерировано скриптом `scripts/scrape_studlab.py`.",
                "",
                "## Файлы",
                "",
                "- `studlab_faculties.csv` — факультеты",
                "- `studlab_training_centers.csv` — учебные центры, встреченные в аудиториях",
                "- `studlab_laboratories.csv` — лаборатории (страницы `/N` на studlab)",
                "- `studlab_rooms.csv` — аудиторный фонд внутри лабораторий",
                "- `studlab_staff.csv` — руководители и сотрудники лабораторий",
                "",
                "## Важно",
                "",
                "- `department_hint` — эвристика из названия/описания, проверьте вручную.",
                "- `role_suggestion` — только подсказка (`LAB_HEAD` / `LAB_ADMIN`).",
                "- Для импорта в labbooking пока используйте как справочник; прямой `--type` ещё нет.",
                "",
                "## Перегенерация",
                "",
                "```bash",
                "python scripts/scrape_studlab.py",
                "python scripts/scrape_studlab.py --faculty neftegaz",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print()
    print(f"Wrote {len(faculties)} faculties, {len(training_centers)} training centers")
    print(f"Wrote {len(laboratories)} laboratories, {len(rooms)} rooms, {len(staff)} staff rows")
    print(f"Output: {output_dir.resolve()}")
    return 0


def normalize_draft(input_dir: Path | None = None) -> Path:
    """Normalize default studlab draft directory (used after scraping)."""
    base = input_dir or Path("docs/csv_templates/studlab_draft")
    argv = ["normalize_studlab_draft.py", "--input", str(base), "--output", str(base)]
    import sys

    old_argv = sys.argv
    try:
        sys.argv = argv
        main()
    finally:
        sys.argv = old_argv
    return base


if __name__ == "__main__":
    raise SystemExit(main())
