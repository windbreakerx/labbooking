from pathlib import Path

import pytest
from django.core.management import call_command

from apps.academics.models import Department, Discipline, Faculty, LabWork, Semester, StudentGroup
from apps.academics.services.curated_catalog_import import import_department_draft
from apps.academics.services.studlab_import import import_studlab_draft
from apps.scheduling.models import Laboratory, TrainingCenter


@pytest.fixture
def semester(db):
    return Semester.objects.create(name="Весна 2025/2026", is_active=True)


@pytest.fixture
def studlab_and_lab(db):
    call_command("import_studlab_org", "docs/csv_templates/studlab_draft")
    return Laboratory.objects.filter(name__icontains="металлургии").first() or Laboratory.objects.first()


@pytest.mark.django_db
def test_import_metallurgy_draft_creates_curriculum(semester, studlab_and_lab):
    repo_root = Path(__file__).resolve().parents[4]
    draft_dir = repo_root / "docs" / "csv_templates" / "metallurgy_draft"
    if not (draft_dir / "01_department.csv").is_file():
        pytest.skip("metallurgy_draft not present")

    stats = import_department_draft(
        draft_dir,
        semester=semester,
        studlab_dir=repo_root / "docs" / "csv_templates" / "studlab_draft",
    )
    assert stats["disciplines"] > 0
    assert stats["lab_works"] > 0
    assert Discipline.objects.filter(code__startswith="MET-").exists()
    assert LabWork.objects.exists()

    group = StudentGroup.objects.filter(name="АПГ-21").first()
    if group:
        assert group.disciplines.exists()
        assert group.lab_works.exists() or group.disciplines.exists()

    assert TrainingCenter.objects.filter(number=1).exists()


@pytest.mark.django_db
def test_studlab_import_updates_existing_department_by_title():
    repo_root = Path(__file__).resolve().parents[4]
    studlab_dir = repo_root / "docs" / "csv_templates" / "studlab_draft"
    if not (studlab_dir / "03_departments.csv").is_file():
        pytest.skip("studlab_draft not present")

    faculty = Faculty.objects.create(code="НГФ", title="Нефтегазовый факультет")
    Department.objects.create(title="Кафедра бурения скважин", faculty=faculty)

    import_studlab_draft(studlab_dir)

    department = Department.objects.get(title="Кафедра бурения скважин")
    assert department.short_code == "БС"
    assert Department.objects.filter(title="Кафедра бурения скважин").count() == 1


@pytest.mark.django_db
def test_studlab_import_truncates_long_lab_short_name():
    repo_root = Path(__file__).resolve().parents[4]
    studlab_dir = repo_root / "docs" / "csv_templates" / "studlab_draft"
    if not (studlab_dir / "04_laboratories.csv").is_file():
        pytest.skip("studlab_draft not present")

    import_studlab_draft(studlab_dir)

    for laboratory in Laboratory.objects.all():
        assert len(laboratory.short_name) <= 64
        assert len(laboratory.name) <= 256
