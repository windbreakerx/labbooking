"""Приёмочные тесты видимости на пилотных данных seed_demo."""

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academics.models import Discipline
from apps.academics.querysets import (
    staff_disciplines_qs,
    student_disciplines_qs,
)
from apps.users.models import User


def _api_result_ids(client, url: str) -> set[int]:
    ids: set[int] = set()
    next_url = url
    while next_url:
        response = client.get(next_url)
        assert response.status_code == 200
        payload = response.json()
        ids.update(item["id"] for item in payload["results"])
        next_url = payload.get("next")
    return ids


@pytest.fixture(scope="module", autouse=True)
def seed_pilot_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo", weeks=1, full_pilot=True)


@pytest.fixture
def tng_student(db):
    return User.objects.get(email="student001@stud.local")


@pytest.fixture
def eht_student(db):
    return User.objects.get(email="student048@stud.local")


@pytest.fixture
def ngs_student(db):
    return User.objects.get(email="student069@stud.local")


@pytest.fixture
def operator(db):
    return User.objects.get(email="operator1.pilot@spmi.ru")


@pytest.fixture
def lab_head(db):
    return User.objects.get(email="zavlab.pilot@spmi.ru")


@pytest.fixture
def transport_discipline(db):
    return Discipline.objects.get(code="NGF-001")


@pytest.fixture
def drilling_discipline(db):
    return Discipline.objects.get(code="NGF-012")


@pytest.fixture
def development_discipline(db):
    return Discipline.objects.get(code="NGF-025")


@pytest.mark.django_db
class TestPilotStudentVisibility:
    def test_tng_student_sees_transport_only(
        self,
        tng_student,
        transport_discipline,
        drilling_discipline,
        development_discipline,
    ):
        ids = set(student_disciplines_qs(tng_student).values_list("pk", flat=True))
        assert transport_discipline.pk in ids
        assert drilling_discipline.pk not in ids
        assert development_discipline.pk not in ids

    def test_eht_student_sees_development_only(
        self,
        eht_student,
        transport_discipline,
        development_discipline,
    ):
        ids = set(student_disciplines_qs(eht_student).values_list("pk", flat=True))
        assert development_discipline.pk in ids
        assert transport_discipline.pk not in ids

    def test_ngs_student_sees_drilling_only(
        self,
        ngs_student,
        transport_discipline,
        drilling_discipline,
    ):
        ids = set(student_disciplines_qs(ngs_student).values_list("pk", flat=True))
        assert drilling_discipline.pk in ids
        assert transport_discipline.pk not in ids

    def test_tng_student_web_hides_foreign_discipline(
        self,
        tng_student,
        transport_discipline,
        drilling_discipline,
    ):
        client = Client()
        client.force_login(tng_student)
        response = client.get("/disciplines/")
        assert response.status_code == 200
        content = response.content.decode()
        assert transport_discipline.title in content
        assert drilling_discipline.title not in content

    def test_tng_student_foreign_discipline_api_404(self, tng_student, drilling_discipline):
        client = APIClient()
        client.force_authenticate(user=tng_student)
        response = client.get(f"/api/v1/disciplines/{drilling_discipline.pk}/lab-works/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestPilotStaffVisibility:
    def test_operator_sees_all_lab_disciplines(self, operator):
        assert staff_disciplines_qs(operator).count() == 31

    def test_operator_web_lists_lab_disciplines(self, operator, transport_discipline, drilling_discipline):
        client = Client()
        client.force_login(operator)
        response = client.get("/staff/disciplines/")
        assert response.status_code == 200
        content = response.content.decode()
        assert transport_discipline.title in content
        assert drilling_discipline.title in content

    def test_operator_api_scoped_to_lab(self, operator, transport_discipline, drilling_discipline):
        client = APIClient()
        client.force_authenticate(user=operator)
        expected_count = staff_disciplines_qs(operator).count()
        response = client.get("/api/v1/disciplines/")
        assert response.status_code == 200
        assert response.json()["count"] == expected_count
        ids = _api_result_ids(client, "/api/v1/disciplines/")
        assert transport_discipline.pk in ids
        assert drilling_discipline.pk in ids


@pytest.mark.django_db
class TestPilotLabHeadVisibility:
    def test_lab_head_role_and_lab_binding(self, lab_head):
        assert lab_head.role == "LAB_HEAD"
        assert lab_head.profile.training_center is not None
        assert lab_head.profile.training_center.number == 1

    def test_lab_head_can_open_dashboard(self, lab_head):
        client = Client()
        client.force_login(lab_head)
        response = client.get(reverse("lab-head-home"))
        assert response.status_code == 200
        assert "Кабинет завлаба" in response.content.decode()

    def test_lab_head_sees_lab_disciplines(self, lab_head, transport_discipline, drilling_discipline):
        ids = set(staff_disciplines_qs(lab_head).values_list("pk", flat=True))
        assert transport_discipline.pk in ids
        assert drilling_discipline.pk in ids

    def test_lab_head_can_open_bindings(self, lab_head):
        client = Client()
        client.force_login(lab_head)
        response = client.get(reverse("lab-head-bindings"))
        assert response.status_code == 200

    def test_operator_cannot_open_lab_head_dashboard(self, operator):
        client = Client()
        client.force_login(operator)
        response = client.get(reverse("lab-head-home"))
        assert response.status_code == 302
