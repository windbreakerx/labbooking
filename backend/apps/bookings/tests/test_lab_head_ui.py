import pytest
from django.urls import reverse

from apps.academics.models import ALLOWED_LAB_DURATIONS, Discipline, LabWork, Semester
from apps.scheduling.models import LabStand, Laboratory, Room, ScheduleEntry, TrainingCenter
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
    return TrainingCenter.objects.create(number=21, name="Учебный центр завлаба")


@pytest.fixture
def own_laboratory(own_tc):
    return Laboratory.objects.create(training_center=own_tc, name="Лаборатория завлаба")


@pytest.fixture
def foreign_tc():
    return TrainingCenter.objects.create(number=22, name="Учебный центр чужой")


@pytest.fixture
def foreign_laboratory(foreign_tc):
    return Laboratory.objects.create(training_center=foreign_tc, name="Чужая лаборатория")


@pytest.fixture
def lab_head(db, own_tc, own_laboratory):
    user = User.objects.create_user(
        email="lab-head-ui@spmi.ru",
        password="pass",
        first_name="Zav",
        last_name="Lab",
        role=UserRole.LAB_HEAD,
        is_staff=True,
    )
    user.profile.training_center = own_tc
    user.profile.laboratory = own_laboratory
    user.profile.save(update_fields=["training_center", "laboratory"])
    return user


@pytest.fixture
def staff_admin(db, own_tc, own_laboratory):
    user = User.objects.create_user(
        email="staff-ui@spmi.ru",
        password="pass",
        first_name="Staff",
        last_name="Admin",
        role=UserRole.LAB_ADMIN,
        is_staff=True,
    )
    user.profile.training_center = own_tc
    user.profile.laboratory = own_laboratory
    user.profile.save(update_fields=["training_center", "laboratory"])
    return user


@pytest.fixture
def own_discipline(semester, own_laboratory, own_tc):
    d = Discipline.objects.create(title="Дисциплина завлаба", semester=semester, is_published=True)
    d.laboratories.add(own_laboratory)
    d.training_centers.add(own_tc)
    return d


@pytest.fixture
def foreign_discipline(semester, foreign_laboratory, foreign_tc):
    d = Discipline.objects.create(title="Чужая дисциплина", semester=semester, is_published=True)
    d.laboratories.add(foreign_laboratory)
    d.training_centers.add(foreign_tc)
    return d


@pytest.fixture
def own_room(own_tc):
    return Room.objects.create(training_center=own_tc, number="101", capacity=10)


@pytest.fixture
def own_stand(own_tc, own_room):
    return LabStand.objects.create(
        name="Стенд завлаба",
        inventory_number="ST-101",
        training_center=own_tc,
        room=own_room,
    )


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
    def test_bind_discipline_to_lab(self, client_logged_in, own_laboratory, foreign_discipline):
        response = client_logged_in.post(
            reverse("lab-head-discipline-bind", kwargs={"pk": foreign_discipline.pk}),
        )
        assert response.status_code == 302
        assert foreign_discipline.laboratories.filter(pk=own_laboratory.pk).exists()

    def test_unbind_discipline_from_lab(self, client_logged_in, own_laboratory, own_discipline):
        response = client_logged_in.post(
            reverse("lab-head-discipline-unbind", kwargs={"pk": own_discipline.pk}),
        )
        assert response.status_code == 302
        assert not own_discipline.laboratories.filter(pk=own_laboratory.pk).exists()

    def test_create_lab_work(self, client_logged_in, own_laboratory, own_discipline, own_room, own_stand):
        response = client_logged_in.post(
            reverse("lab-head-lab-work-create"),
            {
                "discipline": own_discipline.pk,
                "laboratory": own_laboratory.pk,
                "default_room": own_room.pk,
                "number": 2,
                "title": "Новая ЛР",
                "duration_minutes": 60,
                "capacity": 3,
                "primary_stand": own_stand.pk,
            },
        )
        assert response.status_code == 302
        lab_work = LabWork.objects.get(discipline=own_discipline, number=2)
        assert lab_work.capacity == 3
        assert lab_work.default_room_id == own_room.pk
        assert lab_work.primary_stand_id == own_stand.pk
        assert lab_work.laboratories.filter(pk=own_laboratory.pk).exists()

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

    def test_bindings_search_by_title(self, client_logged_in, own_discipline, foreign_discipline, own_laboratory):
        foreign_discipline.laboratories.add(own_laboratory)
        response = client_logged_in.get(reverse("lab-head-bindings"), {"q": "завлаба"})
        assert response.status_code == 200
        content = response.content.decode()
        assert own_discipline.title in content
        assert foreign_discipline.title not in content

    def test_update_lab_work(self, client_logged_in, own_laboratory, own_discipline, own_room, own_stand):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=3,
            title="ЛР для редактирования",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        lab_work.training_centers.add(own_laboratory.training_center)
        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": lab_work.pk}),
            {
                "title": "ЛР обновлённая",
                "number": 3,
                "discipline": own_discipline.pk,
                "laboratory": own_laboratory.pk,
                "default_room": own_room.pk,
                "duration_minutes": 60,
                "capacity": 3,
                "is_published": "on",
                "primary_stand": own_stand.pk,
            },
        )
        assert response.status_code == 302
        lab_work.refresh_from_db()
        assert lab_work.capacity == 3
        assert lab_work.title == "ЛР обновлённая"
        assert lab_work.duration_minutes == 60
        assert lab_work.default_room_id == own_room.pk
        assert lab_work.primary_stand_id == own_stand.pk
        assert lab_work.is_published is True

    def test_unpublish_lab_work(self, client_logged_in, own_laboratory, own_discipline):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=4,
            title="ЛР для снятия",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": lab_work.pk}),
            {
                "title": lab_work.title,
                "number": lab_work.number,
                "discipline": own_discipline.pk,
                "laboratory": own_laboratory.pk,
                "duration_minutes": lab_work.duration_minutes,
                "capacity": lab_work.capacity,
            },
        )
        assert response.status_code == 302
        lab_work.refresh_from_db()
        assert lab_work.is_published is False


@pytest.mark.django_db
class TestLabHeadLabWorksSearch:
    @pytest.fixture
    def own_lab_work(self, own_discipline, own_laboratory, own_room):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=7,
            title="Измерение сопротивления",
            duration_minutes=90,
            capacity=15,
            is_published=True,
            default_room=own_room,
        )
        lab_work.laboratories.add(own_laboratory)
        lab_work.training_centers.add(own_laboratory.training_center)
        return lab_work

    def test_search_by_title(self, client_logged_in, own_lab_work):
        response = client_logged_in.get(reverse("lab-head-lab-works"), {"q": "сопротив"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_lab_work.title in content

    def test_search_by_discipline(self, client_logged_in, own_lab_work, own_discipline):
        response = client_logged_in.get(reverse("lab-head-lab-works"), {"q": "завлаба"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_lab_work.title in content
        assert own_discipline.title in content

    def test_search_by_number(self, client_logged_in, own_lab_work):
        response = client_logged_in.get(reverse("lab-head-lab-works"), {"q": "7"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_lab_work.title in content

    def test_search_by_room(self, client_logged_in, own_lab_work, own_room):
        response = client_logged_in.get(reverse("lab-head-lab-works"), {"q": own_room.number})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_lab_work.title in content

    def test_search_no_results(self, client_logged_in, own_lab_work):
        response = client_logged_in.get(reverse("lab-head-lab-works"), {"q": "несуществующий запрос xyz"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_lab_work.title not in content
        assert "ничего не найдено" in content


@pytest.mark.django_db
class TestLabHeadStandsSearch:
    @pytest.fixture
    def own_stand(self, own_tc, own_room):
        return LabStand.objects.create(
            name="Осциллограф Tektronix",
            inventory_number="INV-042",
            training_center=own_tc,
            room=own_room,
            description="Стенд для лаборатории электроники",
        )

    def test_search_by_name(self, client_logged_in, own_stand):
        response = client_logged_in.get(reverse("lab-head-stands"), {"q": "осцилл"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_stand.name in content

    def test_search_by_inventory_number(self, client_logged_in, own_stand):
        response = client_logged_in.get(reverse("lab-head-stands"), {"q": "INV-042"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_stand.name in content

    def test_search_by_room(self, client_logged_in, own_stand, own_room):
        response = client_logged_in.get(reverse("lab-head-stands"), {"q": own_room.number})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_stand.name in content

    def test_search_no_results(self, client_logged_in, own_stand):
        response = client_logged_in.get(reverse("lab-head-stands"), {"q": "несуществующий стенд xyz"})
        content = response.content.decode()
        assert response.status_code == 200
        assert own_stand.name not in content
        assert "ничего не найдено" in content


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
        own_laboratory,
        own_room,
    ):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=1,
            title="ЛР 1",
            duration_minutes=90,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        lab_work.training_centers.add(own_laboratory.training_center)
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

    def test_create_lab_work_rejects_invalid_duration(self, client_logged_in, own_laboratory, own_discipline):
        response = client_logged_in.post(
            reverse("lab-head-lab-work-create"),
            {
                "discipline": own_discipline.pk,
                "laboratory": own_laboratory.pk,
                "number": 5,
                "title": "ЛР с неверной длительностью",
                "duration_minutes": 35,
                "capacity": 3,
            },
        )
        assert response.status_code == 302
        assert not LabWork.objects.filter(title="ЛР с неверной длительностью").exists()

    def test_update_lab_work_rejects_invalid_duration(self, client_logged_in, own_laboratory, own_discipline):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=10,
            title="ЛР для проверки длительности",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": lab_work.pk}),
            {
                "title": lab_work.title,
                "number": lab_work.number,
                "discipline": own_discipline.pk,
                "laboratory": own_laboratory.pk,
                "duration_minutes": 35,
                "capacity": 5,
                "is_published": "on",
            },
        )
        assert response.status_code == 302
        lab_work.refresh_from_db()
        assert lab_work.duration_minutes == 90

    def test_schedule_rejects_invalid_duration(
        self,
        client_logged_in,
        own_discipline,
        own_laboratory,
        own_room,
    ):
        lab_work = LabWork.objects.create(
            discipline=own_discipline,
            number=11,
            title="ЛР для расписания",
            duration_minutes=90,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        lab_work.training_centers.add(own_laboratory.training_center)
        response = client_logged_in.post(
            reverse("lab-head-schedule-create"),
            {
                "lab_work": lab_work.pk,
                "room": own_room.pk,
                "weekday": 0,
                "start_time": "10:35",
                "week_parity": "BOTH",
                "capacity": 10,
                "duration_minutes": 35,
            },
        )
        assert response.status_code == 302
        assert not ScheduleEntry.objects.filter(lab_work=lab_work, room=own_room, duration_minutes=35).exists()

    def test_allowed_durations_constant(self):
        assert ALLOWED_LAB_DURATIONS == (30, 45, 60, 90)


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
