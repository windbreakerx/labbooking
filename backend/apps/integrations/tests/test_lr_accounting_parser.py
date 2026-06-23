from pathlib import Path

import pytest

from apps.integrations.lr_accounting.parser import (
    detect_header_layout,
    looks_like_person_name,
    parse_workbook,
    room_number_for_file,
)

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


@pytest.mark.skipif(not LABS_DIR.is_dir(), reason="Excel files not available locally")
def test_grp21_disciplines_and_lab_works():
    workbook = parse_workbook(LABS_DIR / "ЛР_учет 1123 весна 25-26.xlsx")
    group = next(sheet for sheet in workbook.group_sheets if sheet.name == "ГРП-21")

    disciplines = {lab.discipline for lab in group.lab_works}
    assert disciplines == {
        "Эксплуатация сетей газораспределения и газопотребления",
        "Монтаж и ремонт газового оборудования",
    }

    by_discipline: dict[str, set[str]] = {}
    for lab in group.lab_works:
        by_discipline.setdefault(lab.discipline, set()).add(lab.title)

    assert "Подготовка ГРУ к запуску. Запуск ГРУ. Настройка ПЗК и ПСК" in by_discipline[
        "Эксплуатация сетей газораспределения и газопотребления"
    ]
    assert "Настройка ПЗК и ПСК" in by_discipline["Эксплуатация сетей газораспределения и газопотребления"]
    assert "Перевод ГРУ на резервную линию редуцирования" in by_discipline[
        "Эксплуатация сетей газораспределения и газопотребления"
    ]
    assert "Сварка ПЭ трубопровода нагретым инструментом в стык" in by_discipline[
        "Монтаж и ремонт газового оборудования"
    ]
    assert "Врезка в газопровод под давлением" in by_discipline["Монтаж и ремонт газового оборудования"]
    assert "Пневматические испытания газопровода" in by_discipline["Монтаж и ремонт газового оборудования"]

    assert any(student.last_name == "Александрук" for student in group.students)


def test_looks_like_person_name():
    assert looks_like_person_name("Александрук Богдан Сергеевич")
    assert not looks_like_person_name("Эксплуатация сетей газораспределения и газопотребления")
    assert not looks_like_person_name("ГРУППА ГРП-22 руководитель лабораторных занятий")


def test_detect_header_layout_variants():
    standard_rows = [
        [],
        [None, None, "Дисциплина А", None, None, "Дисциплина Б"],
        [None, "ГРУППА ... руководитель", "Лаб 1", "Лаб 2", None, None, "Лаб 3"],
    ]
    assert detect_header_layout(standard_rows) == (1, 2)

    compact_rows = [
        [None, None, "Дисциплина А"],
        [None, "ГРУППА ...", "Лаб 1", "Лаб 2"],
        [1, "Иванов Иван Иванович"],
    ]
    assert detect_header_layout(compact_rows) == (0, 1)

    delayed_rows = [
        [],
        [],
        [None, None, "Дисциплина А"],
        [None, "ГРУППА ...", "Лаб 1", "Лаб 2", "Лаб 3"],
    ]
    assert detect_header_layout(delayed_rows) == (2, 3)
