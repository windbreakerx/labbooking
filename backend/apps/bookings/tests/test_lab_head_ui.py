import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import ALLOWED_LAB_DURATIONS, Discipline, LabWork, LabWorkMethodics, Semester
from apps.bookings.models import Booking
from apps.bookings.tests.conftest import create_lab_work
from apps.scheduling.models import LabSession, LabSessionStatus, LabStand, Laboratory, Room, ScheduleEntry, TrainingCenter
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
def own_discipline_secondary(semester, own_laboratory, own_tc):
    d = Discipline.objects.create(title="Заканчивание скважин", semester=semester, is_published=True)
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

    def test_lab_head_people_page_renders(self, client_logged_in, staff_admin):
        response = client_logged_in.get(reverse("lab-head-people"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "На доработке" not in content
        assert staff_admin.email in content

    def test_lab_head_schedule_page_stub(self, client_logged_in):
        response = client_logged_in.get(reverse("lab-head-schedule"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "На доработке" in content
        assert "Раздел временно недоступен" in content

    def test_staff_cannot_open_lab_head_pages(self, client, staff_admin):
        client.force_login(staff_admin)
        response = client.get(reverse("lab-head-home"))
        assert response.status_code == 302

    def test_anonymous_redirected(self, client):
        response = client.get(reverse("lab-head-home"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestLabHeadPeople:
    def test_bind_staff_member(self, client_logged_in, own_tc, own_laboratory):
        teacher = User.objects.create_user(
            email="teacher.unbound@spmi.ru",
            password="pass",
            first_name="Пётр",
            last_name="Препод",
            role=UserRole.TEACHER,
        )
        response = client_logged_in.post(
            reverse("lab-head-person-bind"),
            {"person_id": teacher.pk},
        )
        assert response.status_code == 302
        teacher.profile.refresh_from_db()
        assert teacher.profile.training_center_id == own_tc.pk
        assert teacher.profile.laboratory_id == own_laboratory.pk

    def test_bind_requires_selection(self, client_logged_in):
        response = client_logged_in.post(reverse("lab-head-person-bind"), {})
        assert response.status_code == 302
        assert User.objects.filter(profile__laboratory__isnull=False, role=UserRole.TEACHER).count() == 0

    def test_person_search_excludes_already_bound(self, client_logged_in, staff_admin):
        response = client_logged_in.get(
            reverse("lab-head-person-search"),
            {"q": staff_admin.email},
        )
        assert response.status_code == 200
        assert staff_admin.email not in response.content.decode()

    def test_person_search_finds_unbound(self, client_logged_in):
        teacher = User.objects.create_user(
            email="search.teacher@spmi.ru",
            password="pass",
            first_name="Иван",
            last_name="Иванов",
            role=UserRole.TEACHER,
        )
        response = client_logged_in.get(
            reverse("lab-head-person-search"),
            {"q": teacher.email},
        )
        assert response.status_code == 200
        assert teacher.email in response.content.decode()

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
                "disciplines": [own_discipline.pk],
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
        lab_work = LabWork.objects.get(disciplines=own_discipline, number=2)
        assert lab_work.capacity == 3
        assert lab_work.default_room_id == own_room.pk
        assert lab_work.primary_stand_id == own_stand.pk
        assert lab_work.laboratories.filter(pk=own_laboratory.pk).exists()
        assert lab_work.code is not None
        assert lab_work.code.startswith("НГФ-")

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
        lab_work = create_lab_work(
            own_discipline,
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
                "disciplines": [own_discipline.pk],
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
        lab_work = create_lab_work(
            own_discipline,
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
                "disciplines": [own_discipline.pk],
                "laboratory": own_laboratory.pk,
                "duration_minutes": lab_work.duration_minutes,
                "capacity": lab_work.capacity,
            },
        )
        assert response.status_code == 302
        lab_work.refresh_from_db()
        assert lab_work.is_published is False

    def test_delete_lab_work(self, client_logged_in, own_laboratory, own_discipline):
        lab_work = create_lab_work(
            own_discipline,
            number=6,
            title="ЛР для удаления",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        lab_work_id = lab_work.pk
        response = client_logged_in.post(reverse("lab-head-lab-work-delete", kwargs={"pk": lab_work_id}))
        assert response.status_code == 302
        assert not LabWork.objects.filter(pk=lab_work_id).exists()

    def test_unpublish_lab_work_with_same_number_in_another_discipline(
        self,
        client_logged_in,
        own_laboratory,
        own_discipline,
        own_discipline_secondary,
    ):
        first_lab_work = create_lab_work(
            own_discipline,
            number=1,
            title="ЛР для снятия публикации",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        first_lab_work.laboratories.add(own_laboratory)
        second_lab_work = create_lab_work(
            own_discipline_secondary,
            number=1,
            title="Другая ЛР №1",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        second_lab_work.laboratories.add(own_laboratory)
        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": first_lab_work.pk}),
            {
                "title": first_lab_work.title,
                "number": first_lab_work.number,
                "disciplines": [own_discipline.pk],
                "laboratory": own_laboratory.pk,
                "duration_minutes": first_lab_work.duration_minutes,
                "capacity": first_lab_work.capacity,
            },
        )
        assert response.status_code == 302
        first_lab_work.refresh_from_db()
        assert first_lab_work.is_published is False

    def test_delete_lab_work(self, client_logged_in, own_laboratory, own_discipline):
        from apps.academics.models import LabWork

        lab_work = create_lab_work(
            own_discipline,
            number=5,
            title="ЛР для удаления",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        lab_work_id = lab_work.pk
        response = client_logged_in.post(reverse("lab-head-lab-work-delete", kwargs={"pk": lab_work_id}))
        assert response.status_code == 302
        assert not LabWork.objects.filter(pk=lab_work_id).exists()

    def test_delete_lab_work_blocked_with_active_booking(
        self,
        client_logged_in,
        own_laboratory,
        own_discipline,
        own_room,
        lab_head,
    ):
        from apps.academics.models import LabWork
        from apps.bookings.models import Booking, BookingStatus

        lab_work = create_lab_work(
            own_discipline,
            number=6,
            title="ЛР с записью",
            duration_minutes=90,
            capacity=10,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        starts = timezone.now() + timezone.timedelta(days=2)
        session = LabSession.objects.create(
            lab_work=lab_work,
            room=own_room,
            semester=own_discipline.semester,
            starts_at=starts,
            ends_at=starts + timezone.timedelta(minutes=90),
            capacity=10,
            status=LabSessionStatus.OPEN,
        )
        Booking.objects.create(
            student=lab_head,
            lab_session=session,
            lab_work=lab_work,
            discipline=own_discipline,
            room=own_room,
            scheduled_at=session.starts_at,
            current_status=BookingStatus.BOOKED,
        )
        response = client_logged_in.post(reverse("lab-head-lab-work-delete", kwargs={"pk": lab_work.pk}))
        assert response.status_code == 302
        assert LabWork.objects.filter(pk=lab_work.pk).exists()

    def test_update_duration_updates_only_free_open_sessions(
        self,
        client_logged_in,
        own_discipline,
        own_laboratory,
        own_room,
        lab_head,
    ):
        lab_work = create_lab_work(
            own_discipline,
            number=12,
            title="ЛР для синка длительности",
            duration_minutes=90,
            capacity=8,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        starts = timezone.now() + timezone.timedelta(days=4)
        free_session = LabSession.objects.create(
            lab_work=lab_work,
            room=own_room,
            semester=own_discipline.semester,
            starts_at=starts,
            ends_at=starts + timezone.timedelta(minutes=90),
            capacity=8,
            status=LabSessionStatus.OPEN,
        )
        booked_session = LabSession.objects.create(
            lab_work=lab_work,
            room=own_room,
            semester=own_discipline.semester,
            starts_at=starts + timezone.timedelta(days=1),
            ends_at=starts + timezone.timedelta(days=1, minutes=90),
            capacity=8,
            status=LabSessionStatus.OPEN,
        )
        Booking.objects.create(
            student=lab_head,
            lab_session=booked_session,
            lab_work=lab_work,
            discipline=own_discipline,
            room=own_room,
            scheduled_at=booked_session.starts_at,
        )

        response = client_logged_in.post(
            reverse("lab-head-lab-work-update", kwargs={"pk": lab_work.pk}),
            {
                "title": lab_work.title,
                "number": lab_work.number,
                "disciplines": [own_discipline.pk],
                "laboratory": own_laboratory.pk,
                "duration_minutes": 60,
                "capacity": lab_work.capacity,
                "is_published": "on",
            },
        )
        assert response.status_code == 302
        free_session.refresh_from_db()
        booked_session.refresh_from_db()
        assert free_session.ends_at == free_session.starts_at + timezone.timedelta(minutes=60)
        assert booked_session.ends_at == booked_session.starts_at + timezone.timedelta(minutes=90)


@pytest.mark.django_db
class TestLabHeadLabWorksSearch:
    @pytest.fixture
    def own_lab_work(self, own_discipline, own_laboratory, own_room):
        lab_work = create_lab_work(
            own_discipline,
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
        stand = LabStand.objects.get(training_center=own_tc, inventory_number="INV-001")
        assert stand.is_published is True

    def test_update_stand(self, client_logged_in, own_stand, own_room):
        response = client_logged_in.post(
            reverse("lab-head-stand-update", kwargs={"pk": own_stand.pk}),
            {
                "name": "Стенд обновлён",
                "inventory_number": "INV-UPD",
                "room": own_room.pk,
                "description": "Новое описание",
            },
        )
        assert response.status_code == 302
        own_stand.refresh_from_db()
        assert own_stand.name == "Стенд обновлён"
        assert own_stand.inventory_number == "INV-UPD"
        assert own_stand.description == "Новое описание"

    def test_unpublish_stand(self, client_logged_in, own_stand, own_room):
        response = client_logged_in.post(
            reverse("lab-head-stand-update", kwargs={"pk": own_stand.pk}),
            {
                "name": own_stand.name,
                "inventory_number": own_stand.inventory_number,
                "room": own_room.pk,
            },
        )
        assert response.status_code == 302
        own_stand.refresh_from_db()
        assert own_stand.is_published is False

    def test_delete_stand(self, client_logged_in, own_stand):
        stand_id = own_stand.pk
        response = client_logged_in.post(reverse("lab-head-stand-delete", kwargs={"pk": stand_id}))
        assert response.status_code == 302
        assert not LabStand.objects.filter(pk=stand_id).exists()

    def test_create_schedule_entry(
        self,
        client_logged_in,
        semester,
        own_discipline,
        own_laboratory,
        own_room,
    ):
        lab_work = create_lab_work(
            own_discipline,
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
                "disciplines": [own_discipline.pk],
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
        lab_work = create_lab_work(
            own_discipline,
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
                "disciplines": [own_discipline.pk],
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
        lab_work = create_lab_work(
            own_discipline,
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
class TestLabHeadRoomDisciplines:
    def test_bind_disciplines_to_room(
        self,
        client_logged_in,
        own_room,
        own_discipline,
        own_discipline_secondary,
    ):
        response = client_logged_in.post(
            reverse("lab-head-room-update", kwargs={"pk": own_room.pk}),
            {
                "name": "Аудитория 101",
                "disciplines": [own_discipline.pk, own_discipline_secondary.pk],
            },
        )
        assert response.status_code == 302
        own_room.refresh_from_db()
        bound_ids = set(own_room.disciplines.values_list("pk", flat=True))
        assert own_discipline.pk in bound_ids
        assert own_discipline_secondary.pk in bound_ids

    def test_clear_room_disciplines(self, client_logged_in, own_room, own_discipline):
        own_room.disciplines.add(own_discipline)
        response = client_logged_in.post(
            reverse("lab-head-room-update", kwargs={"pk": own_room.pk}),
            {"name": own_room.name},
        )
        assert response.status_code == 302
        own_room.refresh_from_db()
        assert own_room.disciplines.count() == 0


@pytest.mark.django_db
class TestLabHeadDisciplineFolders:
    @pytest.fixture
    def department_folder(self, db):
        from apps.academics.models import Department

        return Department.objects.create(title="Кафедра тестовая")

    def test_create_department_folder(self, client_logged_in):
        response = client_logged_in.post(
            reverse("lab-head-department-create"),
            {"title": "Новая папка"},
        )
        assert response.status_code == 302
        from apps.academics.models import Department

        assert Department.objects.filter(title="Новая папка").exists()

    def test_assign_discipline_to_folder(
        self,
        client_logged_in,
        own_discipline,
        department_folder,
    ):
        response = client_logged_in.post(
            reverse("lab-head-discipline-department", kwargs={"pk": own_discipline.pk}),
            {"department": department_folder.pk},
        )
        assert response.status_code == 302
        own_discipline.refresh_from_db()
        assert own_discipline.department_id == department_folder.pk

    def test_clear_discipline_folder(self, client_logged_in, own_discipline, department_folder):
        own_discipline.department = department_folder
        own_discipline.save(update_fields=["department"])
        response = client_logged_in.post(
            reverse("lab-head-discipline-department", kwargs={"pk": own_discipline.pk}),
            {"department": ""},
        )
        assert response.status_code == 302
        own_discipline.refresh_from_db()
        assert own_discipline.department_id is None

    def test_delete_empty_department_folder(self, client_logged_in, department_folder):
        response = client_logged_in.post(
            reverse("lab-head-department-delete", kwargs={"pk": department_folder.pk}),
        )
        assert response.status_code == 302
        from apps.academics.models import Department

        assert not Department.objects.filter(pk=department_folder.pk).exists()

    def test_delete_department_folder_moves_disciplines(
        self,
        client_logged_in,
        own_discipline,
        department_folder,
    ):
        own_discipline.department = department_folder
        own_discipline.save(update_fields=["department"])
        response = client_logged_in.post(
            reverse("lab-head-department-delete", kwargs={"pk": department_folder.pk}),
        )
        assert response.status_code == 302
        own_discipline.refresh_from_db()
        assert own_discipline.department_id is None
        from apps.academics.models import Department

        assert not Department.objects.filter(pk=department_folder.pk).exists()


@pytest.mark.django_db
class TestLabHeadLabWorkMethodics:
    @pytest.fixture
    def own_lab_work(self, own_discipline, own_laboratory):
        lab_work = create_lab_work(
            own_discipline,
            number=20,
            title="ЛР для методичек",
            duration_minutes=90,
            is_published=True,
        )
        lab_work.laboratories.add(own_laboratory)
        return lab_work

    def test_upload_multiple_methodics(self, client_logged_in, own_lab_work):
        files = [
            SimpleUploadedFile("guide1.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            SimpleUploadedFile("guide2.pdf", b"%PDF-1.4 test2", content_type="application/pdf"),
        ]
        response = client_logged_in.post(
            reverse("lab-head-lab-work-methodics-upload", kwargs={"pk": own_lab_work.pk}),
            {"methodics_files": files},
        )
        assert response.status_code == 302
        assert own_lab_work.methodics_files.count() == 2

    def test_delete_methodics(self, client_logged_in, own_lab_work):
        methodics = LabWorkMethodics.objects.create(
            lab_work=own_lab_work,
            file=SimpleUploadedFile("guide.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        response = client_logged_in.post(
            reverse(
                "lab-head-lab-work-methodics-delete",
                kwargs={"pk": own_lab_work.pk, "methodics_id": methodics.pk},
            ),
        )
        assert response.status_code == 302
        assert not LabWorkMethodics.objects.filter(pk=methodics.pk).exists()

    def test_staff_can_upload_methodics(self, client, staff_admin, own_lab_work):
        client.force_login(staff_admin)
        file = SimpleUploadedFile("staff-guide.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        response = client.post(
            reverse("staff-lab-work-upload", kwargs={"pk": own_lab_work.pk}),
            {"methodics_files": [file]},
        )
        assert response.status_code == 302
        assert own_lab_work.methodics_files.count() == 1


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
