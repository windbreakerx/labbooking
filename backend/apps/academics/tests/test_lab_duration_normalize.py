import pytest

from apps.academics.services.catalog_normalize import normalize_lab_duration


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (20, 30),
        (30, 30),
        (39, 45),
        (45, 45),
        (52, 60),
        (60, 60),
        (67, 90),
        (90, 90),
        (135, 90),
    ],
)
def test_normalize_lab_duration_rounds_up(raw, expected):
    assert normalize_lab_duration(raw) == expected


def test_normalize_lab_duration_none():
    assert normalize_lab_duration(None) is None
    assert normalize_lab_duration(None, default=90) == 90
