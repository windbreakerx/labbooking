from django.db.models import QuerySet

from apps.academics.models import Discipline, LabWork, Semester
from apps.academics.querysets import (
    resolve_staff_training_center,
    staff_managed_disciplines_qs,
    staff_managed_lab_works_qs,
)
from apps.scheduling.models import Room, ScheduleEntry, TrainingCenter
from apps.users.models import User, UserRole


def is_lab_head_user(user: User) -> bool:
    return user.is_authenticated and user.role == UserRole.LAB_HEAD


def lab_head_training_center(user: User) -> TrainingCenter | None:
    return resolve_staff_training_center(user)


def lab_head_people_qs(user: User) -> QuerySet[User]:
    tc = lab_head_training_center(user)
    if not tc:
        return User.objects.none()
    return (
        User.objects.filter(
            role__in=[UserRole.LAB_ADMIN, UserRole.TEACHER],
            profile__training_center=tc,
        )
        .select_related("profile", "profile__training_center")
        .prefetch_related("profile__disciplines")
        .order_by("last_name", "first_name")
    )


def lab_head_bindable_disciplines_qs(user: User) -> QuerySet[Discipline]:
    tc = lab_head_training_center(user)
    if not tc:
        return Discipline.objects.none()
    return (
        Discipline.objects.filter(semester__is_active=True)
        .exclude(training_centers=tc)
        .order_by("title")
    )


def lab_head_bindable_lab_works_qs(user: User) -> QuerySet[LabWork]:
    tc = lab_head_training_center(user)
    if not tc:
        return LabWork.objects.none()
    discipline_ids = staff_managed_disciplines_qs(user).values_list("pk", flat=True)
    return (
        LabWork.objects.filter(discipline_id__in=discipline_ids)
        .exclude(training_centers=tc)
        .select_related("discipline")
        .order_by("discipline__title", "number")
    )


def lab_head_teachers_qs(user: User) -> QuerySet[User]:
    tc = lab_head_training_center(user)
    if not tc:
        return User.objects.none()
    return User.objects.filter(
        role=UserRole.TEACHER,
        profile__training_center=tc,
    ).order_by("last_name", "first_name")


def lab_head_rooms_qs(user: User) -> QuerySet[Room]:
    tc = lab_head_training_center(user)
    if not tc:
        return Room.objects.none()
    return Room.objects.filter(training_center=tc).select_related("training_center").order_by("number")


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
    tc = lab_head_training_center(user)
    semester = lab_head_active_semester()
    if not tc:
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
    discipline.training_centers.add(tc)
    return discipline


def lab_head_person_in_scope(user: User, person_id: int) -> User | None:
    return lab_head_people_qs(user).filter(pk=person_id).first()


def lab_head_discipline_in_scope(user: User, discipline_id: int) -> Discipline | None:
    return staff_managed_disciplines_qs(user).filter(pk=discipline_id).first()


def lab_head_lab_work_in_scope(user: User, lab_work_id: int) -> LabWork | None:
    return staff_managed_lab_works_qs(user).filter(pk=lab_work_id).first()
