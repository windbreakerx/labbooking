from pathlib import Path

import pytest

from apps.integrations.lr_accounting.parser import parse_workbook, room_number_for_file

LABS_DIR = Path(r"d:\Users\Mayorov_IV\Desktop\labs")


@pytest.mark.skipif(not LABS_DIR.is_dir(), reason="Excel files not available locally")
@pytest.mark.parametrize(
    ("filename", "room"),
    [
        ("ЛР_учет 2115 весна 25-26.xlsx", "2115"),
        ("ЛР_учет 2116-18 весна 25-26.xlsx", "2118"),
        ("ЛР_учет 2114-16 весна 25-26.xlsx", "2114"),
        ("ЛР_учет 2117 весна 25-26.xlsx", "2117"),
        ("ЛР_учет 1123 весна 25-26.xlsx", "1123"),
    ],
)
def test_room_number_for_file(filename, room):
    assert room_number_for_file(LABS_DIR / filename) == room


@pytest.mark.skipif(not LABS_DIR.is_dir(), reason="Excel files not available locally")
def test_parse_workbook_has_groups_and_catalog():
    workbook = parse_workbook(LABS_DIR / "ЛР_учет 1123 весна 25-26.xlsx")
    assert workbook.room_number == "1123"
    assert workbook.group_sheets
    assert workbook.catalog
    assert any(group.students for group in workbook.group_sheets)
