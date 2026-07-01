from pathlib import Path

import pytest

from apps.academics.services.workload_students import (
    collect_group_targets,
    normalize_student_count,
)


def test_normalize_student_count_caps_outliers():
    assert normalize_student_count(285, max_per_group=40) == 40
    assert normalize_student_count(24, max_per_group=40) == 24
    assert normalize_student_count(0, max_per_group=40) == 0


@pytest.mark.django_db
def test_collect_group_targets_filters_academic_year():
    repo_root = Path(__file__).resolve().parents[4]
    templates_dir = repo_root / "docs" / "csv_templates"
    if not (templates_dir / "metallurgy_draft" / "03_groups.csv").is_file():
        pytest.skip("workload drafts not present")

    all_years = collect_group_targets(templates_dir, academic_year=None, max_per_group=40)
    current_year = collect_group_targets(
        templates_dir,
        academic_year="2025-2026",
        max_per_group=40,
    )

    assert len(current_year) < len(all_years)
    assert sum(current_year.values()) < sum(all_years.values())
    assert all(count <= 40 for count in current_year.values())
