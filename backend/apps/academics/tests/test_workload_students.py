from pathlib import Path

import csv
import pytest

from apps.academics.services.workload_students import (
    SANE_STUDENT_COUNT_MAX,
    collect_group_targets,
    normalize_student_count,
)


def test_normalize_student_count_rejects_outliers():
    assert normalize_student_count(285) == 28
    assert normalize_student_count(24) == 24
    assert normalize_student_count(0) == 0


def test_collect_group_targets_fixed_five_per_group():
    repo_root = Path(__file__).resolve().parents[4]
    templates_dir = repo_root / "docs" / "csv_templates"
    if not (templates_dir / "metallurgy_draft" / "03_groups.csv").is_file():
        pytest.skip("workload drafts not present")

    targets = collect_group_targets(
        templates_dir,
        academic_year="2025-2026",
        students_per_group=5,
    )
    assert targets
    assert all(count == 5 for count in targets.values())


def test_collect_group_targets_dedupes_group_across_years():
    repo_root = Path(__file__).resolve().parents[4]
    templates_dir = repo_root / "docs" / "csv_templates"
    met_groups = templates_dir / "metallurgy_draft" / "03_groups.csv"
    if not met_groups.is_file():
        pytest.skip("workload drafts not present")

    names_all_years: set[str] = set()
    with met_groups.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("group_name") or "").strip()
            if name:
                names_all_years.add(name)

    targets = collect_group_targets(
        templates_dir,
        academic_year=None,
        students_per_group=5,
    )
    met_in_targets = names_all_years & set(targets)
    assert len(met_in_targets) == len(names_all_years)
    assert all(targets[name] == 5 for name in met_in_targets)


@pytest.mark.django_db
def test_collect_group_targets_filters_academic_year():
    repo_root = Path(__file__).resolve().parents[4]
    templates_dir = repo_root / "docs" / "csv_templates"
    if not (templates_dir / "metallurgy_draft" / "03_groups.csv").is_file():
        pytest.skip("workload drafts not present")

    all_years = collect_group_targets(templates_dir, academic_year=None, students_per_group=5)
    current_year = collect_group_targets(
        templates_dir,
        academic_year="2025-2026",
        students_per_group=5,
    )

    assert len(current_year) < len(all_years)
    assert sum(current_year.values()) == len(current_year) * 5
    assert SANE_STUDENT_COUNT_MAX == 28
