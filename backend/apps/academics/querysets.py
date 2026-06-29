from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, QuerySet

from apps.academics.models import Department, Discipline, LabWork, StudentGroup
from apps.scheduling.models import Laboratory, TrainingCenter
from apps.users.models import User, UserRole


def _safe_profile(user: User):
    try:
        return user.profile
    except (AttributeError, ObjectDoesNotExist):
        return None


def department_discipline_groups(
    disciplines,
    *,
    departments=None,
) -> list[dict]:
    discipline_list = list(disciplines)
    if departments is None:
        department_ids = {d.department_id for d in discipline_list if d.department_id}
        department_list = list(
            Department.objects.filter(pk__in=department_ids).order_by("ordering", "title")
        )
    else:
        department_list = list(departments)

    groups: list[dict] = []
    assigned_ids: set[int] = set()
    for department in department_list:
        dept_disciplines = [d for d in discipline_list if d.department_id == department.pk]
        assigned_ids.update(d.pk for d in dept_disciplines)
        groups.append({"department": department, "disciplines": dept_disciplines})
    unassigned = [d for d in discipline_list if d.pk not in assigned_ids]
    if unassigned:
        groups.append({"department": None, "disciplines": unassigned})
    return groups


def published_disciplines_qs():
    return Discipline.objects.filter(
        is_published=True,
        semester__is_active=True,
    )


def published_lab_works_qs(discipline_id: int):
    return LabWork.objects.filter(
        disciplines=discipline_id,
        is_published=True,
        disciplines__semester__is_active=True,
    ).distinct()


def lab_works_for_discipline_qs(discipline_id: int | None = None) -> QuerySet[LabWork]:
    qs = LabWork.objects.filter(disciplines__semester__is_active=True)
    if discipline_id is not None:
        qs = qs.filter(disciplines=discipline_id)
    return qs.distinct()


def resolve_student_group(user: User) -> StudentGroup | None:
    profile = _safe_profile(user)
    if not profile:
        return None
    if profile.student_group_id:
        return profile.student_group
    if profile.group_name:
        return StudentGroup.objects.filter(name=profile.group_name).first()
    return None


def student_disciplines_qs(user: User) -> QuerySet[Discipline]:
    qs = published_disciplines_qs()
    group = resolve_student_group(user)
    if not group:
        return qs.none()
    return qs.filter(student_groups=group)


def student_lab_works_qs(user: User, discipline_id: int | None = None) -> QuerySet[LabWork]:
    group = resolve_student_group(user)
    if not group:
        return LabWork.objects.none()

    qs = LabWork.objects.filter(
        is_published=True,
        disciplines__semester__is_active=True,
    ).distinct()
    if discipline_id is not None:
        qs = qs.filter(disciplines=discipline_id)

    if group.lab_works.exists():
        return qs.filter(student_groups=group)
    return qs.filter(disciplines__student_groups=group).distinct()


def student_can_access_discipline(user: User, discipline_id: int) -> bool:
    if user.role != UserRole.STUDENT:
        return True
    return student_disciplines_qs(user).filter(pk=discipline_id).exists()


def student_can_access_lab_work(user: User, lab_work_id: int) -> bool:
    if user.role != UserRole.STUDENT:
        return True
    return student_lab_works_qs(user).filter(pk=lab_work_id).exists()


def student_support_training_centers_qs(user: User) -> QuerySet[TrainingCenter]:
    group = resolve_student_group(user)
    if not group:
        return TrainingCenter.objects.none()

    discipline_ids = student_disciplines_qs(user).values_list("pk", flat=True)
    lab_work_ids = student_lab_works_qs(user).values_list("pk", flat=True)
    return TrainingCenter.objects.filter(
        Q(disciplines__in=discipline_ids) | Q(lab_works__in=lab_work_ids)
    ).distinct()


def student_rooms_qs(user: User):
    from apps.scheduling.models import Room

    if user.role != UserRole.STUDENT:
        return Room.objects.none()

    lab_work_ids = student_lab_works_qs(user).values_list("pk", flat=True)
    discipline_ids = student_disciplines_qs(user).values_list("pk", flat=True)
    tc_ids = student_support_training_centers_qs(user).values_list("pk", flat=True)
    if not tc_ids:
        return Room.objects.none()

    return (
        Room.objects.filter(training_center__in=tc_ids)
        .filter(Q(default_lab_works__in=lab_work_ids) | Q(disciplines__in=discipline_ids))
        .distinct()
        .select_related("training_center")
        .prefetch_related("disciplines", "stands")
        .order_by("number")
    )


def student_room_in_scope(user: User, room_id: int):
    return student_rooms_qs(user).filter(pk=room_id).first()


def resolve_staff_training_center(user: User) -> TrainingCenter | None:
    profile = _safe_profile(user)
    if not profile:
        return None
    if profile.laboratory_id:
        return profile.laboratory.training_center
    return profile.training_center


def resolve_staff_laboratory(user: User) -> Laboratory | None:
    profile = _safe_profile(user)
    if not profile:
        return None
    if profile.laboratory_id:
        return profile.laboratory
    tc = profile.training_center
    if not tc:
        return None
    return tc.laboratories.order_by("name").first()


def staff_people_qs(user: User) -> QuerySet[User]:
    """Сотрудники и преподаватели в зоне доступа staff/lab-head."""
    qs = User.objects.filter(
        role__in=[UserRole.LAB_ADMIN, UserRole.TEACHER],
    ).select_related("profile", "profile__training_center", "profile__laboratory")
    if user.role == UserRole.SYS_ADMIN:
        return qs.order_by("last_name", "first_name", "email")
    laboratory = resolve_staff_laboratory(user)
    if laboratory:
        return qs.filter(profile__laboratory=laboratory).order_by("last_name", "first_name", "email")
    tc = resolve_staff_training_center(user)
    if not tc:
        return User.objects.none()
    return qs.filter(profile__training_center=tc).order_by("last_name", "first_name", "email")


def staff_disciplines_qs(user: User) -> QuerySet[Discipline]:
    """Опубликованные дисциплины активного семестра в лаборатории сотрудника."""
    qs = published_disciplines_qs()
    if user.role == UserRole.SYS_ADMIN:
        return qs
    laboratory = resolve_staff_laboratory(user)
    if laboratory:
        return qs.filter(laboratories=laboratory)
    tc = resolve_staff_training_center(user)
    if not tc:
        return qs.none()
    return qs.filter(training_centers=tc)


def staff_managed_disciplines_qs(user: User) -> QuerySet[Discipline]:
    """Все дисциплины лаборатории для панели сотрудника."""
    qs = Discipline.objects.select_related("semester", "department")
    if user.role == UserRole.SYS_ADMIN:
        return qs.order_by("title")
    laboratory = resolve_staff_laboratory(user)
    if laboratory:
        return qs.filter(laboratories=laboratory).order_by("title")
    tc = resolve_staff_training_center(user)
    if not tc:
        return Discipline.objects.none()
    return qs.filter(training_centers=tc).order_by("title")


def staff_lab_works_qs(user: User, discipline_id: int | None = None) -> QuerySet[LabWork]:
    qs = LabWork.objects.filter(
        is_published=True,
        disciplines__semester__is_active=True,
    ).distinct()
    if discipline_id is not None:
        qs = qs.filter(disciplines=discipline_id)
    if user.role == UserRole.SYS_ADMIN:
        return qs
    laboratory = resolve_staff_laboratory(user)
    if laboratory:
        return qs.filter(laboratories=laboratory)
    tc = resolve_staff_training_center(user)
    if not tc:
        return LabWork.objects.none()
    return qs.filter(training_centers=tc)


def staff_managed_lab_works_qs(user: User) -> QuerySet[LabWork]:
    qs = LabWork.objects.prefetch_related("disciplines", "disciplines__department")
    if user.role == UserRole.SYS_ADMIN:
        return qs.order_by("number", "title")
    laboratory = resolve_staff_laboratory(user)
    if laboratory:
        return qs.filter(laboratories=laboratory).order_by("number", "title")
    tc = resolve_staff_training_center(user)
    if not tc:
        return LabWork.objects.none()
    return qs.filter(training_centers=tc).order_by("number", "title")


def staff_can_access_discipline(user: User, discipline_id: int) -> bool:
    if user.role == UserRole.STUDENT:
        return student_can_access_discipline(user, discipline_id)
    if user.role == UserRole.SYS_ADMIN:
        return True
    if user.role in {UserRole.LAB_ADMIN, UserRole.LAB_HEAD, UserRole.TEACHER}:
        return staff_disciplines_qs(user).filter(pk=discipline_id).exists()
    return published_disciplines_qs().filter(pk=discipline_id).exists()


def staff_can_access_lab_work(user: User, lab_work_id: int) -> bool:
    if user.role == UserRole.STUDENT:
        return student_can_access_lab_work(user, lab_work_id)
    if user.role == UserRole.SYS_ADMIN:
        return True
    if user.role in {UserRole.LAB_ADMIN, UserRole.LAB_HEAD, UserRole.TEACHER}:
        return staff_lab_works_qs(user).filter(pk=lab_work_id).exists()
    return LabWork.objects.filter(
        pk=lab_work_id,
        is_published=True,
        disciplines__semester__is_active=True,
    ).exists()
