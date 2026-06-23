import pytest
from django.urls import reverse

from apps.academics.models import Discipline, LabWork, Semester
from apps.scheduling.models import LabStand, Room, ScheduleEntry, TrainingCenter
from apps.users.models import User, UserRole


@pytest.fixture
def semester(db):
    return Semester.objects.create(
        name="Lab Head UI",
        start_date="2026-01-01",
        end_date="2026-12-31",
        is_active=True,
    )


@pytest.fixture
def own_tc():
    return TrainingCenter.objects.create(number=21, name="Лаборатория завлаба")


@pytest.fixture
def foreign_tc():
    return TrainingCenter.objects.create(number=22, name="Чужая лаборатория")


@pytest.fixture
def lab_head(db, own_tc):
    user = User.objects.create_user(
        email="lab-head-ui@spmi.ru",
        password="pass",
        first_name="Zav",
        last_name="Lab",
        role=UserRole.LAB_HEAD,
        is_staff=True,
    )
    user.profile.training_center = own_tc
    user.profile.save(update_fields=["training_center"])
    return user


@pytest.fixture
def staff_admin(db, own_tc):
    user = User.objects.create_user(
        email="staff-ui@spmi.ru",
        password="pass",
        first_name="Staff",
        last_name="Admin",
        role=UserRole.LAB_ADMIN,
        is_staff=True,
    )
    user.profile.training_center = own_tc
    user.profile.save(update_fields=["training_center"])
    return user


@pytest.fixture
def own_discipline(semester, own_tc):
    d = Discipline.objects.create(title="Дисциплина завлаба", semester=semester, is_published=True)
    d.training_centers.add(own_tc)
    return d


@pytest.fixture
def foreign_discipline(semester, foreign_tc):
    d = Discipline.objects.create(title="Чужая дисциплина", semester=semester, is_published=True)
    d.training_centers.add(foreign_tc)
    return d


@pytest.fixture
def own_room(own_tc):
    return Room.objects.create(training_center=own_tc, number="101", capacity=10)


@pytest.fixture
def client_logged_in(client, lab_head):
    client.force_login(lab_head)
    return client


@pytest.mark.django_db
class TestLabHeadUIAccess:
    def test_lab_head_can_open_dashboard(self, client_logged_in):
        response = client_logged_in.get(reverse("lab-head-home"))
        assert response.status_code == 200
        assert "Кабинет завлаба" in response.content.decode()

    def test_staff_cannot_open_lab_head_pages(self, client, staff_admin):
        client.force_login(staff_admin)
        response = client.get(reverse("lab-head-home"))
        assert response.status_code == 302

    def test_anonymous_redirected(self, client):
        response = client.get(reverse("lab-head-home"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestLabHeadPeople:
    def test_create_staff_member(self, client_logged_in, own_tc):
        response = client_logged_in.post(
            reverse("lab-head-person-create"),
            {
                "email": "new.staff@spmi.ru",
                "first_name": "Новый",
                "last_name": "Сотрудник",
                "role": UserRole.LAB_ADMIN,
                "password": "TempPass123!",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(email="new.staff@spmi.ru")
        assert user.role == UserRole.LAB_ADMIN
        assert user.profile.training_center_id == own_tc.pk

    def test_bind_disciplines_to_person(self, client_logged_in, own_discipline, staff_admin):
        response = client_logged_in.post(
            reverse("lab-head-person-bindings", kwargs={"pk": staff_admin.pk}),
            {"disciplines": [own_discipline.pk]},
        )
        assert response.status_code == 302
        staff_admin.profile.refresh_from_db()
        assert list(staff_admin.profile.disciplines.values_list("pk", flat=True)) == [own_discipline.pk]


@pytest.mark.django_db
class TestLabHeadBindings:
    def test_bind_discipline_to_lab(self, client_logged_in, own_tc, foreign_discipline):
        response = client_logged_in.post(
            reverse("lab-head-discipline-bind", kwargs={"pk": foreign_discipline.pk}),
        )
        assert response.status_code == 302
        assert foreign_discipline.training_centers.filter(pk=own_tc.pk).exists()

    def test_unbind_discipline_from_lab(self, client_logged_in, own_tc, own_discipline):
        response = client_logged_in.post(
            reverse("lab-head-discipline-unbind", kwargs={"pk": own_discipline.pk}),
        )
        assert response.status_code == 302
        assert not own_discipline.training_centers.filter(pk=own_tc.pk).exists()

    def test_create_lab_work(self, client_logged_in, own_tc, own_discipline, own_room):
        response = client_logged_in.post(
            reverse("lab-head-lab-work-create"),
            {
                "discipline": own_discipline.pk,
                "training_center": own_tc.pk,
                "default_room": own_room.pk,
                "number": 2,
                "title": "Новая ЛР",
                "duration_minutes": 90,
                "capacity": 3,
            },
        )
        assert response.status_code == 302
        lab_work = LabWork.objects.get(discipline=own_discipline, number=2)
        assert lab_work.capacity == 3
        assert lab_work.default_room_id == own_room.pk
        assert lab_work.training_centers.filter(pk=own_tc.pk).exists()

    def test_create_discipline_disabled_for_lab_head(self, client_logged_in, own_tc, semester):
        response = client_logged_in.post(
            reverse("lab-head-discipline-create"),
            {
                "title": "Новая дисциплина",
                "description": "Описание",
            },
        )
        assert response.status_code == 302
        assert not Discipline.objects.filter(title="Новая дисциплина").exists()

    def test_bindings_search_by_title(self, client_logged_in, own_discipline, foreign_discipline, own_tc):
        foreign_discipline.training_centers.add(own_tc)
        response = client_logged_in.get(reverse("lab-head-bindings"), {"q": "завлаба"})
        assert response.status_code == 200
        content = response.content.decode()
        assert own_discipline.title in content
        assert foreign_discipline.title not in content

    def test_update_lab_work(self, client_logged_in, own_tc, own_discipline, own_room):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=3,
            title="ЛР для редактирования",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.training_centers.add(own_tc)
        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": lab_work.pk}),
            {
                "title": "ЛР обновлённая",
                "number": 3,
                "discipline": own_discipline.pk,
                "training_center": own_tc.pk,
                "default_room": own_room.pk,
                "duration_minutes": 120,
                "capacity": 3,
                "is_published": "on",
            },
        )
        assert response.status_code == 302
        lab_work.refresh_from_db()
        assert lab_work.capacity == 3
        assert lab_work.title == "ЛР обновлённая"
        assert lab_work.duration_minutes == 120
        assert lab_work.default_room_id == own_room.pk
        assert lab_work.is_published is True

    def test_unpublish_lab_work(self, client_logged_in, own_tc, own_discipline):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=4,
            title="ЛР для снятия",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.training_centers.add(own_tc)
        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": lab_work.pk}),
            {
                "title": lab_work.title,
                "number": lab_work.number,
                "discipline": own_discipline.pk,
                "training_center": own_tc.pk,
                "duration_minutes": lab_work.duration_minutes,
                "capacity": lab_work.capacity,
            },
        )
        assert response.status_code == 302
        lab_work.refresh_from_db()
        assert lab_work.is_published is False


@pytest.mark.django_db
class TestLabHeadStandsAndSchedule:
    def test_create_stand(self, client_logged_in, own_tc, own_room):
        response = client_logged_in.post(
            reverse("lab-head-stand-create"),
            {
                "name": "Стенд А",
                "inventory_number": "INV-001",
                "room": own_room.pk,
            },
        )
        assert response.status_code == 302
        assert LabStand.objects.filter(training_center=own_tc, inventory_number="INV-001").exists()

    def test_create_schedule_entry(
        self,
        client_logged_in,
        semester,
        own_discipline,
        own_tc,
        own_room,
    ):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=1,
            title="ЛР 1",
            duration_minutes=90,
            is_published=True,
        )
        lab_work.training_centers.add(own_tc)
        response = client_logged_in.post(
            reverse("lab-head-schedule-create"),
            {
                "lab_work": lab_work.pk,
                "room": own_room.pk,
                "weekday": 0,
                "start_time": "10:35",
                "week_parity": "BOTH",
                "capacity": 10,
                "duration_minutes": 90,
            },
        )
        assert response.status_code == 302
        assert ScheduleEntry.objects.filter(lab_work=lab_work, room=own_room).exists()


@pytest.mark.django_db
class TestStaffCannotManageLabResources:
    def test_staff_cannot_create_stand_via_staff_url(self, client, staff_admin, own_room):
        client.force_login(staff_admin)
        before = LabStand.objects.count()
        response = client.post(
            reverse("staff-stand-create"),
            {
                "name": "Чужой стенд",
                "inventory_number": "X-1",
                "training_center": own_room.training_center_id,
                "room": own_room.pk,
            },
        )
        assert response.status_code == 302
        assert LabStand.objects.count() == before
