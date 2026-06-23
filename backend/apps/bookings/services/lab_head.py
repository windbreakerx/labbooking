from django.db.models import Q, QuerySet

from apps.academics.models import Discipline, LabWork, Semester
from apps.academics.querysets import (
    resolve_staff_laboratory,
    resolve_staff_training_center,
    staff_managed_disciplines_qs,
    staff_managed_lab_works_qs,
)
from apps.scheduling.models import LabStand, Laboratory, Room, ScheduleEntry, TrainingCenter
from apps.users.models import User, UserRole


def is_lab_head_user(user: User) -> bool:
    return user.is_authenticated and user.role == UserRole.LAB_HEAD


def lab_head_training_center(user: User) -> TrainingCenter | None:
    return resolve_staff_training_center(user)


def lab_head_laboratory(user: User) -> Laboratory | None:
    return resolve_staff_laboratory(user)


def sync_training_centers_for_laboratories(obj) -> None:
    tc_ids = obj.laboratories.values_list("training_center_id", flat=True).distinct()
    obj.training_centers.set(tc_ids)


def lab_head_people_qs(user: User) -> QuerySet[User]:
    laboratory = lab_head_laboratory(user)
    tc = lab_head_training_center(user)
    if not laboratory and not tc:
        return User.objects.none()
    filters = {"role__in": [UserRole.LAB_ADMIN, UserRole.TEACHER]}
    if laboratory:
        filters["profile__laboratory"] = laboratory
    elif tc:
        filters["profile__training_center"] = tc
    return (
        User.objects.filter(**filters)
        .select_related("profile", "profile__training_center", "profile__laboratory")
        .prefetch_related("profile__disciplines")
        .order_by("last_name", "first_name")
    )


def _published_search_q(query: str) -> Q:
    lower = query.lower()
    if lower in {"да", "yes"}:
        return Q(is_published=True)
    if lower in {"нет", "no"}:
        return Q(is_published=False)
    if "опублик" in lower:
        return Q(is_published=True)
    if "снят" in lower or "скрыт" in lower:
        return Q(is_published=False)
    return Q()


def lab_head_lab_work_search_q(query: str) -> Q:
    query = (query or "").strip()
    if not query:
        return Q()

    search_q = (
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(discipline__title__icontains=query)
        | Q(laboratories__name__icontains=query)
        | Q(training_centers__name__icontains=query)
        | Q(default_room__number__icontains=query)
        | _published_search_q(query)
    )
    if query.isdigit():
        number = int(query)
        search_q |= Q(number=number) | Q(duration_minutes=number) | Q(capacity=number)
        search_q |= Q(training_centers__number=number)
    return search_q


def filter_lab_head_lab_works(qs: QuerySet[LabWork], query: str) -> QuerySet[LabWork]:
    search_q = lab_head_lab_work_search_q(query)
    if not search_q:
        return qs
    return qs.filter(search_q).distinct()


def lab_head_stand_search_q(query: str) -> Q:
    query = (query or "").strip()
    if not query:
        return Q()

    search_q = (
        Q(name__icontains=query)
        | Q(inventory_number__icontains=query)
        | Q(description__icontains=query)
        | Q(room__number__icontains=query)
    )
    if query.isdigit():
        search_q |= Q(training_center__number=int(query))
    return search_q


def filter_lab_head_stands(qs: QuerySet[LabStand], query: str) -> QuerySet[LabStand]:
    search_q = lab_head_stand_search_q(query)
    if not search_q:
        return qs
    return qs.filter(search_q).distinct()


def lab_head_bindable_disciplines_qs(user: User) -> QuerySet[Discipline]:
    laboratory = lab_head_laboratory(user)
    if not laboratory:
        return Discipline.objects.none()
    return (
        Discipline.objects.filter(semester__is_active=True)
        .exclude(laboratories=laboratory)
        .order_by("title")
    )


def lab_head_bindable_lab_works_qs(user: User) -> QuerySet[LabWork]:
    laboratory = lab_head_laboratory(user)
    if not laboratory:
        return LabWork.objects.none()
    discipline_ids = staff_managed_disciplines_qs(user).values_list("pk", flat=True)
    return (
        LabWork.objects.filter(discipline_id__in=discipline_ids)
        .exclude(laboratories=laboratory)
        .select_related("discipline")
        .order_by("discipline__title", "number")
    )


def lab_head_teachers_qs(user: User) -> QuerySet[User]:
    laboratory = lab_head_laboratory(user)
    tc = lab_head_training_center(user)
    if not laboratory and not tc:
        return User.objects.none()
    filters = {"role": UserRole.TEACHER}
    if laboratory:
        filters["profile__laboratory"] = laboratory
    else:
        filters["profile__training_center"] = tc
    return User.objects.filter(**filters).order_by("last_name", "first_name")


def lab_head_rooms_qs(user: User) -> QuerySet[Room]:
    tc = lab_head_training_center(user)
    if not tc:
        return Room.objects.none()
    return Room.objects.filter(training_center=tc).select_related("training_center").order_by("number")


def lab_head_training_centers_qs(user: User) -> QuerySet[TrainingCenter]:
    tc = lab_head_training_center(user)
    if not tc:
        return TrainingCenter.objects.none()
    return TrainingCenter.objects.filter(pk=tc.pk).order_by("number")


def lab_head_laboratories_qs(user: User) -> QuerySet[Laboratory]:
    tc = lab_head_training_center(user)
    if not tc:
        return Laboratory.objects.none()
    return Laboratory.objects.filter(training_center=tc).select_related("training_center").order_by("name")


def lab_head_room_in_scope(user: User, room_id: int) -> Room | None:
    return lab_head_rooms_qs(user).filter(pk=room_id).first()


def lab_head_training_center_in_scope(user: User, training_center_id: int) -> TrainingCenter | None:
    return lab_head_training_centers_qs(user).filter(pk=training_center_id).first()


def lab_head_laboratory_in_scope(user: User, laboratory_id: int) -> Laboratory | None:
    return lab_head_laboratories_qs(user).filter(pk=laboratory_id).first()


def lab_head_schedule_qs(user: User) -> QuerySet[ScheduleEntry]:
    from apps.bookings.services import staff_lab_filter

    qs = ScheduleEntry.objects.select_related(
        "lab_work",
        "lab_work__discipline",
        "room",
        "room__training_center",
        "semester",
        "teacher",
    )
    return staff_lab_filter(qs, user)


def lab_head_active_semester() -> Semester | None:
    return Semester.objects.filter(is_active=True).first()


def lab_head_create_discipline(user: User, *, title: str, description: str = "") -> Discipline:
    laboratory = lab_head_laboratory(user)
    semester = lab_head_active_semester()
    if not laboratory:
        raise ValueError("Лаборатория не указана.")
    if not semester:
        raise ValueError("Нет активного семестра.")
    title = title.strip()
    if not title:
        raise ValueError("Укажите название дисциплины.")

    discipline = Discipline.objects.create(
        title=title,
        description=description.strip(),
        semester=semester,
        is_published=True,
    )
    discipline.code = f"DISC-{discipline.pk}"
    discipline.save(update_fields=["code"])
    discipline.laboratories.add(laboratory)
    sync_training_centers_for_laboratories(discipline)
    return discipline


def lab_head_person_in_scope(user: User, person_id: int) -> User | None:
    return lab_head_people_qs(user).filter(pk=person_id).first()


def lab_head_discipline_in_scope(user: User, discipline_id: int) -> Discipline | None:
    return staff_managed_disciplines_qs(user).filter(pk=discipline_id).first()


def lab_head_lab_work_in_scope(user: User, lab_work_id: int) -> LabWork | None:
    return staff_managed_lab_works_qs(user).filter(pk=lab_work_id).first()


def lab_head_update_lab_work(
    user: User,
    lab_work: LabWork,
    *,
    title: str,
    number: int,
    discipline: Discipline,
    duration_minutes: int,
    capacity: int,
    is_published: bool,
    laboratory: Laboratory,
    default_room: Room | None = None,
) -> LabWork:
    title = title.strip()
    if not title:
        raise ValueError("Укажите название лабораторной работы.")
    if number < 1:
        raise ValueError("Номер ЛР должен быть не меньше 1.")
    if duration_minutes < 30:
        raise ValueError("Длительность должна быть не меньше 30 минут.")
    if capacity < 1:
        raise ValueError("Количество мест должно быть не меньше 1.")
    if not lab_head_discipline_in_scope(user, discipline.pk):
        raise ValueError("Дисциплина недоступна.")
    if not lab_head_laboratory_in_scope(user, laboratory.pk):
        raise ValueError("Лаборатория недоступна.")
    if default_room and default_room.training_center_id != laboratory.training_center_id:
        raise ValueError("Аудитория должна относиться к учебному центру лаборатории.")

    duplicate = LabWork.objects.filter(discipline=discipline, number=number).exclude(pk=lab_work.pk).exists()
    if duplicate:
        raise ValueError(f"ЛР №{number} для этой дисциплины уже существует.")

    capacity_changed = lab_work.capacity != capacity
    lab_work.title = title
    lab_work.number = number
    lab_work.discipline = discipline
    lab_work.duration_minutes = duration_minutes
    lab_work.capacity = capacity
    lab_work.is_published = is_published
    lab_work.default_room = default_room
    lab_work.save(
        update_fields=[
            "title",
            "number",
            "discipline",
            "duration_minutes",
            "capacity",
            "is_published",
            "default_room",
        ]
    )
    lab_work.laboratories.set([laboratory.pk])
    sync_training_centers_for_laboratories(lab_work)
    if capacity_changed:
        from apps.scheduling.services.capacity import sync_open_session_capacities

        sync_open_session_capacities(lab_work)
    return lab_work
