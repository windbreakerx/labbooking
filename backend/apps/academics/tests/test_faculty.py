import pytest

from apps.academics.models import Department, Discipline, Faculty, LabWork, StudentGroup
from apps.bookings.services.lab_head import generate_lab_work_code
from apps.scheduling.models import Laboratory, LaboratoryType, TrainingCenter


@pytest.mark.django_db
class TestFacultyModel:
    def test_faculty_str_and_ordering(self):
        second = Faculty.objects.create(code="ИФ", title="Инженерный факультет", ordering=1)
        first = Faculty.objects.create(code="НГФ", title="Нефтегазовый факультет", ordering=0)
        assert str(first) == "Нефтегазовый факультет"
        assert list(Faculty.objects.values_list("code", flat=True)) == ["НГФ", "ИФ"]

    def test_department_faculty_link(self):
        faculty = Faculty.objects.create(code="НГФ", title="Нефтегазовый факультет")
        department = Department.objects.create(title="Кафедра бурения скважин", faculty=faculty)
        assert department.faculty_id == faculty.pk
        assert list(faculty.departments.values_list("title", flat=True)) == ["Кафедра бурения скважин"]

    def test_student_group_department_nullable(self):
        group = StudentGroup.objects.create(name="TEST-24", faculty="Нефтегазовый")
        assert group.department_id is None

        department = Department.objects.create(title="Кафедра тестовая")
        group.department = department
        group.save(update_fields=["department"])
        assert group.department_id == department.pk


@pytest.mark.django_db
class TestLaboratoryFaculty:
    def test_laboratory_faculty_and_lab_type(self):
        faculty = Faculty.objects.create(code="НГФ", title="Нефтегазовый факультет")
        tc = TrainingCenter.objects.create(number=1, name="УЦ №1")
        lab = Laboratory.objects.create(
            training_center=tc,
            name="Комплексная учебная лаборатория",
            faculty=faculty,
            lab_type=LaboratoryType.COMPLEX,
        )
        assert lab.faculty_id == faculty.pk
        assert lab.lab_type == LaboratoryType.COMPLEX
        assert list(faculty.laboratories.values_list("name", flat=True)) == [lab.name]


@pytest.mark.django_db
class TestGenerateLabWorkCode:
    def test_uses_faculty_from_department_chain(self):
        faculty = Faculty.objects.create(code="НГФ", title="Нефтегазовый факультет")
        department = Department.objects.create(
            title="Кафедра бурения скважин",
            short_code="БС",
            faculty=faculty,
        )
        discipline = Discipline.objects.create(title="Бурение", short_code="БУ", department=department)
        code = generate_lab_work_code(number=1, discipline=discipline)
        assert code == "НГФ-БС-БУ-1"

    def test_fallback_without_department(self):
        discipline = Discipline.objects.create(title="Общая дисциплина", short_code="ОД")
        code = generate_lab_work_code(number=2, discipline=discipline)
        assert code == "НГФ-БК-ОД-2"

    def test_unique_suffix_on_collision(self):
        faculty = Faculty.objects.create(code="НГФ", title="Нефтегазовый факультет")
        department = Department.objects.create(title="Кафедра", short_code="К", faculty=faculty)
        discipline = Discipline.objects.create(title="Дисциплина", short_code="Д", department=department)
        LabWork.objects.create(number=1, title="Existing", code="НГФ-К-Д-1")
        code = generate_lab_work_code(number=1, discipline=discipline)
        assert code == "НГФ-К-Д-1-2"

    def test_no_discipline_uses_defaults(self):
        code = generate_lab_work_code(number=3, discipline=None)
        assert code == "НГФ-БК-ДИС-3"
