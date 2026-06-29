import pytest

from apps.academics.models import Department, Discipline, Faculty, LabWork, StudentGroup
from apps.bookings.services.lab_head import generate_lab_work_code
from apps.scheduling.models import Laboratory, LaboratoryType, TrainingCenter


@pytest.fixture
def ngf_faculty(db):
    faculty, _ = Faculty.objects.get_or_create(
        code="НГФ",
        defaults={
            "title": "Нефтегазовый факультет",
            "ordering": 0,
        },
    )
    return faculty


@pytest.mark.django_db
class TestFacultyModel:
    def test_faculty_str_and_ordering(self, ngf_faculty):
        Faculty.objects.get_or_create(
            code="ИФ",
            defaults={"title": "Инженерный факультет", "ordering": 1},
        )
        assert str(ngf_faculty) == "Нефтегазовый факультет"
        codes = list(Faculty.objects.order_by("ordering", "title").values_list("code", flat=True))
        assert codes[:2] == ["НГФ", "ИФ"]

    def test_department_faculty_link(self, ngf_faculty):
        department = Department.objects.create(
            title="Кафедра тестовая (faculty link)",
            faculty=ngf_faculty,
        )
        assert department.faculty_id == ngf_faculty.pk
        assert list(ngf_faculty.departments.filter(pk=department.pk).values_list("title", flat=True)) == [
            department.title
        ]

    def test_student_group_department_nullable(self):
        group = StudentGroup.objects.create(name="TEST-24", faculty="Нефтегазовый")
        assert group.department_id is None

        department = Department.objects.create(title="Кафедра тестовая (group link)")
        group.department = department
        group.save(update_fields=["department"])
        assert group.department_id == department.pk


@pytest.mark.django_db
class TestLaboratoryFaculty:
    def test_laboratory_faculty_and_lab_type(self, ngf_faculty):
        tc = TrainingCenter.objects.create(number=991, name="УЦ тест faculty")
        lab = Laboratory.objects.create(
            training_center=tc,
            name="Комплексная учебная лаборатория (test)",
            faculty=ngf_faculty,
            lab_type=LaboratoryType.COMPLEX,
        )
        assert lab.faculty_id == ngf_faculty.pk
        assert lab.lab_type == LaboratoryType.COMPLEX
        assert list(ngf_faculty.laboratories.filter(pk=lab.pk).values_list("name", flat=True)) == [lab.name]


@pytest.mark.django_db
class TestGenerateLabWorkCode:
    def test_uses_faculty_from_department_chain(self, ngf_faculty):
        department = Department.objects.create(
            title="Кафедра бурения (test code)",
            short_code="БС",
            faculty=ngf_faculty,
        )
        discipline = Discipline.objects.create(
            title="Бурение (test code)",
            short_code="БУ",
            department=department,
        )
        code = generate_lab_work_code(number=1, discipline=discipline)
        assert code == "НГФ-БС-БУ-1"

    def test_fallback_without_department(self):
        discipline = Discipline.objects.create(title="Общая дисциплина (test code)", short_code="ОД")
        code = generate_lab_work_code(number=2, discipline=discipline)
        assert code == "НГФ-БК-ОД-2"

    def test_unique_suffix_on_collision(self, ngf_faculty):
        department = Department.objects.create(
            title="Кафедра (test collision)",
            short_code="К",
            faculty=ngf_faculty,
        )
        discipline = Discipline.objects.create(
            title="Дисциплина (test collision)",
            short_code="Д",
            department=department,
        )
        LabWork.objects.create(number=1, title="Existing collision", code="НГФ-К-Д-1")
        code = generate_lab_work_code(number=1, discipline=discipline)
        assert code == "НГФ-К-Д-1-2"

    def test_no_discipline_uses_defaults(self):
        code = generate_lab_work_code(number=3, discipline=None)
        assert code == "НГФ-БК-ДИС-3"
