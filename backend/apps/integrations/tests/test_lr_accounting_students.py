import pytest

from apps.integrations.lr_accounting.students import (
    admission_year_from_group,
    allocate_student_id,
    new_year_counters,
    student_email,
)


@pytest.mark.parametrize(
    ("group", "year"),
    [
        ("ТНГ-21", "21"),
        ("СТ-22", "22"),
        ("ЭХТ-22-1", "22"),
        ("НГС-21-1", "21"),
        ("НБ-22", "22"),
    ],
)
def test_admission_year_from_group(group, year):
    assert admission_year_from_group(group) == year


def test_allocate_student_id_and_email():
    counters = new_year_counters()
    first = allocate_student_id("ТНГ-21", counters)
    second = allocate_student_id("СТ-22", counters)
    third = allocate_student_id("ТНГ-21", counters)
    assert first == "210001"
    assert second == "220001"
    assert third == "210002"
    assert student_email(first) == "s210001@stud.spmi.ru"
