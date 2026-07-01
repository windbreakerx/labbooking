import logging
import time

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from apps.bookings.models import (
    AuditLog,
    Booking,
    BookingStatus,
    BookingStatusHistory,
    RegistrationType,
    WaitlistEntry,
)
from apps.bookings.services.session_availability import (
    is_day_open_for_booking,
    is_manual_session_time_allowed,
    is_pair_time_for_booking,
    is_weekday_for_booking,
    booking_date_window,
    lab_work_capacity_would_be_exceeded,
    manual_booking_max_date,
    room_capacity_would_be_exceeded,
)
from apps.academics.models import Discipline
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus
from apps.users.models import User, UserRole

logger = logging.getLogger(__name__)

DEADLOCK_MAX_ATTEMPTS = 3
DEADLOCK_RETRY_BASE_SECONDS = 0.05


class BookingError(Exception):
    pass


ACTIVE_STATUSES = {BookingStatus.BOOKED}
BLOCKING_VISITED_LAB = {BookingStatus.VISITED}


def _is_deadlock_error(exc: OperationalError) -> bool:
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate == "40P01":
        return True
    cause = getattr(exc, "__cause__", None)
    if getattr(cause, "pgcode", None) == "40P01":
        return True
    if getattr(cause, "sqlstate", None) == "40P01":
        return True
    return "deadlock detected" in str(exc).lower()


class BookingService:
    def __init__(self, actor: User | None = None, ip_address: str | None = None):
        self.actor = actor
        self.ip_address = ip_address
        self.booking_warnings: list[str] = []

    def _log_audit(self, action: str, entity_type: str, entity_id: int, payload: dict | None = None):
        AuditLog.objects.create(
            actor=self.actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=self.ip_address,
            payload=payload or {},
        )

    def _record_status(self, booking: Booking, status: str, note: str = ""):
        booking.current_status = status
        booking.save(update_fields=["current_status", "updated_at"])
        BookingStatusHistory.objects.create(
            booking=booking,
            status=status,
            changed_by=self.actor,
            note=note,
        )

    def _validate_booking_window(self, session: LabSession, skip_student_rules: bool = False):
        now = timezone.now()
        session_local_date = timezone.localtime(session.starts_at).date()
        if not skip_student_rules:
            if not is_day_open_for_booking(session_local_date, now):
                min_date, max_date = booking_date_window(now)
                raise BookingError(
                    f"Запись сейчас открыта на даты с {min_date:%d.%m.%Y} по {max_date:%d.%m.%Y}. "
                    f"Ближайший день закрывается в {settings.BOOKING_DAY_CLOSES_AT}, "
                    f"новый дальний день открывается в {settings.BOOKING_DAY_OPENS_AT}."
                )
        if session.starts_at <= now:
            raise BookingError("Нельзя записаться на прошедший слот.")
        if not is_weekday_for_booking(session.starts_at):
            raise BookingError("Запись доступна только в будние дни.")
        if not is_pair_time_for_booking(session.starts_at):
            raise BookingError("Запись доступна только на университетские пары.")
        if session.status != LabSessionStatus.OPEN:
            raise BookingError("Слот недоступен для записи.")
        if Holiday.objects.filter(date=session.starts_at.date()).exists():
            raise BookingError("Запись в праздничный день недоступна.")

    def _validate_manual_booking_window(self, session: LabSession):
        now = timezone.now()
        if not is_manual_session_time_allowed(session, now):
            raise BookingError("Нельзя записаться на прошедший слот.")
        session_local_date = timezone.localtime(session.starts_at).date()
        max_date = manual_booking_max_date(now)
        if session_local_date > max_date:
            raise BookingError(
                f"Ручная запись доступна не далее чем на {settings.MANUAL_BOOKING_WORKING_WEEKS} "
                f"рабочие недели (до {max_date:%d.%m.%Y})."
            )
        if not is_weekday_for_booking(session.starts_at):
            raise BookingError("Запись доступна только в будние дни.")
        if not is_pair_time_for_booking(session.starts_at):
            raise BookingError("Запись доступна только на университетские пары.")
        if session.status != LabSessionStatus.OPEN:
            raise BookingError("Слот недоступен для записи.")
        if Holiday.objects.filter(date=session_local_date).exists():
            raise BookingError("Запись в праздничный день недоступна.")

    def _stand_blocked_by_other_lab_work(self, session: LabSession) -> bool:
        return session.is_stand_blocked_by_other_lab_work()

    def _student_overlap_bookings(self, student: User, session: LabSession):
        return Booking.objects.filter(
            student=student,
            current_status__in=ACTIVE_STATUSES,
            lab_session__starts_at__lt=session.ends_at,
            lab_session__ends_at__gt=session.starts_at,
        ).select_related("lab_work", "lab_session")

    def _overlap_warning_message(self, student: User, session: LabSession) -> str:
        parts = []
        for booking in self._student_overlap_bookings(student, session):
            local = timezone.localtime(booking.scheduled_at)
            parts.append(f"«{booking.lab_work.title}» {local:%d.%m.%Y} в {local:%H:%M}")
        joined = "; ".join(parts)
        return (
            f"У студента уже есть запись на пересекающееся время: {joined}. "
            "Согласуйте время со студентом."
        )

    def _student_overlap_booked(self, student: User, session: LabSession) -> bool:
        return self._student_overlap_bookings(student, session).exists()

    def _lock_session_rows(self, session_ids: list[int] | set[int]):
        unique_sorted = sorted(set(session_ids))
        if not unique_sorted:
            return
        list(
            LabSession.objects.select_for_update(of=("self",))
            .filter(pk__in=unique_sorted)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

    def _overlapping_room_session_ids(self, session: LabSession) -> list[int]:
        return list(
            LabSession.objects.filter(
                room_id=session.room_id,
                starts_at__lt=session.ends_at,
                ends_at__gt=session.starts_at,
            ).values_list("pk", flat=True)
        )

    def _overlapping_stand_session_ids(self, session: LabSession) -> list[int]:
        stand_id = session.lab_work.primary_stand_id
        if not stand_id:
            return []
        return list(
            LabSession.objects.filter(
                lab_work__primary_stand_id=stand_id,
                starts_at__lt=session.ends_at,
                ends_at__gt=session.starts_at,
            ).values_list("pk", flat=True)
        )

    def _overlapping_same_lab_work_session_ids(self, session: LabSession) -> list[int]:
        return list(
            LabSession.objects.filter(
                lab_work_id=session.lab_work_id,
                starts_at__lt=session.ends_at,
                ends_at__gt=session.starts_at,
            ).values_list("pk", flat=True)
        )

    def _collect_booking_lock_ids(self, session: LabSession) -> list[int]:
        lock_ids = {session.pk}
        lock_ids.update(self._overlapping_room_session_ids(session))
        lock_ids.update(self._overlapping_stand_session_ids(session))
        lock_ids.update(self._overlapping_same_lab_work_session_ids(session))
        return sorted(lock_ids)

    def _lock_for_booking(self, session: LabSession):
        """
        Блокирует целевой слот и все пересекающиеся слоты аудитории/стенда
        в фиксированном порядке, чтобы снизить риск deadlock.
        """
        self._lock_session_rows(self._collect_booking_lock_ids(session))

    def _validate_cancel_window(self, booking: Booking, by_staff: bool = False):
        if by_staff:
            return
        deadline = booking.scheduled_at - timezone.timedelta(hours=settings.BOOKING_CANCEL_HOURS)
        if timezone.now() > deadline:
            raise BookingError(
                f"Отмена возможна не позднее чем за {settings.BOOKING_CANCEL_HOURS} часа до начала."
            )

    def _check_discipline_limit(self, student: User, discipline_id: int, lab_work_id: int):
        active = Booking.objects.filter(
            student=student,
            discipline_id=discipline_id,
            current_status__in=ACTIVE_STATUSES,
        ).exists()
        if active:
            raise BookingError("Уже есть активная запись по этой дисциплине.")

        visited_same_lab = Booking.objects.filter(
            student=student,
            lab_work_id=lab_work_id,
            current_status=BookingStatus.VISITED,
        ).exists()
        if visited_same_lab:
            raise BookingError("Вы уже посетили эту лабораторную работу.")

    def create_booking(
        self,
        student: User,
        session_id: int,
        *,
        discipline_id: int | None = None,
        manual: bool = False,
        skip_student_rules: bool = False,
    ) -> Booking:
        self.booking_warnings = []
        last_deadlock: OperationalError | None = None
        for attempt in range(DEADLOCK_MAX_ATTEMPTS):
            try:
                with transaction.atomic():
                    return self._create_booking_in_transaction(
                        student,
                        session_id,
                        discipline_id=discipline_id,
                        manual=manual,
                        skip_student_rules=skip_student_rules,
                    )
            except OperationalError as exc:
                if not _is_deadlock_error(exc):
                    raise
                last_deadlock = exc
                logger.warning(
                    "Deadlock during create_booking, retry %s/%s",
                    attempt + 1,
                    DEADLOCK_MAX_ATTEMPTS,
                    extra={"session_id": session_id, "student_id": student.pk},
                )
                if attempt + 1 >= DEADLOCK_MAX_ATTEMPTS:
                    raise BookingError(
                        "Система обрабатывает параллельные записи. Повторите попытку через несколько секунд."
                    ) from last_deadlock
                time.sleep(DEADLOCK_RETRY_BASE_SECONDS * (attempt + 1))
        raise AssertionError("create_booking retry loop exited without result")

    def _resolve_booking_discipline(
        self,
        student: User,
        lab_work_id: int,
        discipline_id: int | None,
        *,
        manual: bool = False,
        skip_student_rules: bool = False,
    ) -> Discipline:
        discipline_qs = Discipline.objects.filter(lab_works=lab_work_id)
        if discipline_id is not None:
            discipline = discipline_qs.filter(pk=discipline_id).first()
            if discipline is None:
                raise BookingError("Дисциплина недоступна для этой лабораторной работы.")
            if student.role == UserRole.STUDENT and not skip_student_rules:
                from apps.academics.querysets import student_disciplines_qs

                if not student_disciplines_qs(student).filter(pk=discipline_id).exists():
                    raise BookingError("Дисциплина недоступна для этой лабораторной работы.")
            return discipline

        if skip_student_rules:
            discipline = discipline_qs.order_by("title").first()
            if discipline is None:
                raise BookingError("У лабораторной работы нет привязанных дисциплин.")
            return discipline

        from apps.academics.querysets import student_disciplines_qs

        discipline = (
            student_disciplines_qs(student)
            .filter(lab_works=lab_work_id)
            .order_by("title")
            .first()
        )
        if discipline is None:
            raise BookingError("Дисциплина недоступна для этой лабораторной работы.")
        return discipline

    def _create_booking_in_transaction(
        self,
        student: User,
        session_id: int,
        *,
        discipline_id: int | None = None,
        manual: bool = False,
        skip_student_rules: bool = False,
    ) -> Booking:
        if manual and self.actor and not staff_can_modify_bookings(self.actor):
            raise BookingError("Недостаточно прав для ручной записи.")
        session = (
            LabSession.objects.select_related("lab_work", "room")
            .prefetch_related("lab_work__disciplines")
            .get(pk=session_id)
        )
        if student.role == UserRole.STUDENT and not skip_student_rules:
            from apps.academics.querysets import student_can_access_lab_work

            if not student_can_access_lab_work(student, session.lab_work_id):
                raise BookingError("Лабораторная работа недоступна для вашей группы.")
        booking_discipline = self._resolve_booking_discipline(
            student,
            session.lab_work_id,
            discipline_id,
            manual=manual,
            skip_student_rules=skip_student_rules,
        )
        self._lock_for_booking(session)
        if manual:
            self._validate_manual_booking_window(session)
        else:
            self._validate_booking_window(session, skip_student_rules=skip_student_rules)

        if manual:
            if self._stand_blocked_by_other_lab_work(session):
                raise BookingError("Стенд уже занят на это время. Выберите другой интервал.")
            if self._student_overlap_booked(student, session):
                self.booking_warnings.append(self._overlap_warning_message(student, session))
        elif not skip_student_rules:
            self._check_discipline_limit(
                student,
                booking_discipline.pk,
                session.lab_work_id,
            )
            if self._student_overlap_booked(student, session):
                raise BookingError("У вас уже есть запись на пересекающееся время.")

        booked_count = session.bookings.filter(current_status=BookingStatus.BOOKED).count()
        if not manual and not skip_student_rules:
            if booked_count >= session.capacity:
                raise BookingError("Нет свободных мест.")
            if lab_work_capacity_would_be_exceeded(session):
                raise BookingError(
                    "Лимит мест для этой лабораторной работы исчерпан на выбранный интервал. "
                    "Выберите другую пару."
                )
            if room_capacity_would_be_exceeded(session):
                raise BookingError(
                    f"Аудитория {session.room.number} заполнена на это время. Выберите другую пару."
                )
            if self._stand_blocked_by_other_lab_work(session):
                raise BookingError("Стенд уже занят на это время. Выберите другой интервал.")

        booking = Booking.objects.create(
            student=student,
            lab_session=session,
            lab_work=session.lab_work,
            discipline=booking_discipline,
            room=session.room,
            scheduled_at=session.starts_at,
            current_status=BookingStatus.BOOKED,
            registration_type=RegistrationType.MANUAL if manual else RegistrationType.AUTO,
            registered_by=self.actor if manual else None,
        )
        self._record_status(booking, BookingStatus.BOOKED, "Создание записи")
        self._log_audit("booking.create", "Booking", booking.pk, {"session_id": session_id})
        self._send_email(booking, "booked")
        return booking

    @transaction.atomic
    def cancel_booking(self, booking: Booking, by_staff: bool = False) -> Booking:
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if booking.current_status != BookingStatus.BOOKED:
            raise BookingError("Можно отменить только активную запись.")
        self._validate_cancel_window(booking, by_staff=by_staff)
        self._record_status(
            booking,
            BookingStatus.CANCELLED,
            "Отмена сотрудником" if by_staff else "Отмена студентом",
        )
        self._log_audit("booking.cancel", "Booking", booking.pk)
        self._send_email(booking, "cancelled")
        self._promote_waitlist(booking.lab_session)
        return booking

    @transaction.atomic
    def change_status(
        self,
        booking: Booking,
        new_status: str,
        note: str = "",
    ) -> Booking:
        if self.actor and not staff_can_modify_bookings(self.actor):
            raise BookingError("Недостаточно прав для изменения статуса записи.")
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        allowed = {
            BookingStatus.BOOKED,
            BookingStatus.NO_SHOW,
            BookingStatus.CANCELLED,
            BookingStatus.REACCESS,
            BookingStatus.VISITED,
        }
        if new_status not in allowed:
            raise BookingError("Недопустимый статус.")

        if new_status == BookingStatus.NO_SHOW and booking.student.profile:
            profile = booking.student.profile
            profile.no_show_count += 1
            profile.save(update_fields=["no_show_count"])

        self._record_status(booking, new_status, note)
        self._log_audit(
            "booking.status_change",
            "Booking",
            booking.pk,
            {"status": new_status},
        )
        email_map = {
            BookingStatus.NO_SHOW: "no_show",
            BookingStatus.REACCESS: "reaccess",
            BookingStatus.VISITED: "visited",
        }
        if new_status in email_map:
            self._send_email(booking, email_map[new_status])
        return booking

    def _promote_waitlist(self, session: LabSession):
        entry = (
            WaitlistEntry.objects.filter(lab_session=session)
            .order_by("position")
            .select_related("student")
            .first()
        )
        if not entry:
            return
        try:
            self.create_booking(entry.student, session.pk)
            entry.delete()
        except BookingError:
            entry.delete()

    @transaction.atomic
    def join_waitlist(self, student: User, session_id: int) -> WaitlistEntry:
        session = LabSession.objects.select_for_update(of=("self",)).get(pk=session_id)
        if student.role == UserRole.STUDENT:
            from apps.academics.querysets import student_can_access_lab_work

            if not student_can_access_lab_work(student, session.lab_work_id):
                raise BookingError("Лабораторная работа недоступна для вашей группы.")
        if session.bookings.filter(current_status=BookingStatus.BOOKED).count() < session.capacity:
            raise BookingError("В слоте есть свободные места — запишитесь напрямую.")
        if WaitlistEntry.objects.filter(lab_session=session, student=student).exists():
            raise BookingError("Вы уже в очереди на этот слот.")
        position = (
            WaitlistEntry.objects.filter(lab_session=session).count() + 1
        )
        entry = WaitlistEntry.objects.create(
            lab_session=session,
            student=student,
            position=position,
        )
        self._log_audit("waitlist.join", "WaitlistEntry", entry.pk)
        return entry

    @transaction.atomic
    def cancel_session_with_reaccess(self, session: LabSession, note: str = "") -> int:
        """Отмена слота: студентам с активной записью — статус REACCESS."""
        session.status = LabSessionStatus.CANCELLED
        session.save(update_fields=["status"])
        count = 0
        for booking in session.bookings.filter(current_status=BookingStatus.BOOKED):
            self.change_status(
                booking,
                BookingStatus.REACCESS,
                note=note or "Изменение расписания",
            )
            count += 1
        self._log_audit(
            "session.cancel",
            "LabSession",
            session.pk,
            {"reaccess_count": count},
        )
        return count

    def mark_visited_for_ended_sessions(self) -> int:
        """Авто-проставление VISITED для завершённых слотов с активными записями."""
        now = timezone.now()
        count = 0
        sessions = LabSession.objects.filter(
            ends_at__lte=now,
            status=LabSessionStatus.OPEN,
        )
        for session in sessions:
            for booking in session.bookings.filter(current_status=BookingStatus.BOOKED):
                self.change_status(booking, BookingStatus.VISITED, note="Автоматически")
                count += 1
            session.status = LabSessionStatus.CLOSED
            session.save(update_fields=["status"])
        return count

    def _send_email(self, booking: Booking, event: str):
        templates = {
            "booked": (
                "Запись на лабораторную работу",
                (
                    f"Вы записаны на лабораторную работу «{booking.lab_work.title}» "
                    f"по дисциплине «{booking.discipline.title}» "
                    f"{booking.scheduled_at:%d.%m.%Y} в {booking.scheduled_at:%H:%M} "
                    f"в ауд. № {booking.room.number}."
                ),
            ),
            "cancelled": (
                "Отмена записи на лабораторную работу",
                (
                    f"Вы отменили запись на лабораторную работу «{booking.lab_work.title}» "
                    f"по дисциплине «{booking.discipline.title}» "
                    f"{booking.scheduled_at:%d.%m.%Y} в {booking.scheduled_at:%H:%M}."
                ),
            ),
            "visited": (
                "Посещение лабораторной работы",
                (
                    f"Вы посетили лабораторную работу «{booking.lab_work.title}» "
                    f"по дисциплине «{booking.discipline.title}». "
                    f"Можете записаться на другие лабораторные работы по дисциплине."
                ),
            ),
            "no_show": (
                "Неявка на лабораторную работу",
                (
                    f"Вы не посетили лабораторную работу «{booking.lab_work.title}». "
                    f"Обратитесь в лабораторию с объяснительной запиской."
                ),
            ),
            "reaccess": (
                "Повторный доступ к записи",
                (
                    f"Вам предоставлен повторный доступ к записи на "
                    f"лабораторную работу «{booking.lab_work.title}» "
                    f"по дисциплине «{booking.discipline.title}»."
                ),
            ),
        }
        subject, message = templates.get(event, ("Уведомление", ""))
        if message:
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
            try:
                send_mail(
                    subject,
                    message,
                    from_email,
                    [booking.student.email],
                    fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
                )
            except Exception:
                logger.exception(
                    "Failed to send booking email",
                    extra={"booking_id": booking.pk, "event": event},
                )


def is_staff_user(user: User) -> bool:
    return user.role in {
        UserRole.LAB_ADMIN,
        UserRole.LAB_HEAD,
        UserRole.TEACHER,
        UserRole.SYS_ADMIN,
    }


def staff_can_modify_bookings(user: User) -> bool:
    """LAB_ADMIN, LAB_HEAD, SYS_ADMIN may change statuses and manual bookings; TEACHER — read-only."""
    return user.role in {
        UserRole.LAB_ADMIN,
        UserRole.LAB_HEAD,
        UserRole.SYS_ADMIN,
    }


def staff_lab_filter(
    qs,
    user,
    *,
    training_center_lookup: str = "room__training_center",
    laboratory_lookup: str | None = "room__laboratory",
):
    """Scope staff data to own lab (SYS_ADMIN sees all).

    When profile.laboratory is set and laboratory_lookup is provided, filter by
    laboratory (sibling labs in the same training center stay isolated).
    Pass laboratory_lookup=None for models that only expose training_center
    (e.g. SupportTicket).

    Bookings in rooms without laboratory assignment remain visible within the
    same training center as the staff member's laboratory.
    """
    if user.role == UserRole.SYS_ADMIN:
        return qs
    try:
        profile = user.profile
    except (AttributeError, ObjectDoesNotExist):
        profile = None
    if not profile:
        return qs.none()

    tc = profile.training_center
    if profile.laboratory_id:
        tc = profile.laboratory.training_center or tc

    if profile.laboratory_id and laboratory_lookup is not None:
        laboratory = profile.laboratory
        lookup_value = laboratory.pk if laboratory_lookup in {"pk", "id"} else laboratory
        scoped = qs.filter(**{laboratory_lookup: lookup_value})
        if laboratory_lookup == "room__laboratory" and tc:
            lookup_tc = tc.pk if training_center_lookup in {"pk", "id"} else tc
            legacy = qs.filter(
                room__laboratory__isnull=True,
                **{training_center_lookup: lookup_tc},
            )
            return (scoped | legacy).distinct()
        if laboratory_lookup == "laboratory" and tc:
            lookup_tc = tc.pk if training_center_lookup in {"pk", "id"} else tc
            legacy = qs.filter(
                laboratory__isnull=True,
                **{training_center_lookup: lookup_tc},
            )
            return (scoped | legacy).distinct()
        return scoped

    if not tc:
        return qs.none()
    lookup_value = tc.pk if training_center_lookup in {"pk", "id"} else tc
    return qs.filter(**{training_center_lookup: lookup_value})


def staff_can_access_scoped_object(
    user: User,
    qs,
    *,
    training_center_lookup: str = "room__training_center",
    laboratory_lookup: str | None = "room__laboratory",
) -> bool:
    return staff_lab_filter(
        qs,
        user,
        training_center_lookup=training_center_lookup,
        laboratory_lookup=laboratory_lookup,
    ).exists()


BOOKING_SORT_FIELDS: dict[str, tuple[list[str], str]] = {
    "student": (["student__last_name", "student__first_name", "pk"], "asc"),
    "group": (
        ["student__profile__group_name", "student__profile__student_group__name", "pk"],
        "asc",
    ),
    "discipline": (["discipline__title", "pk"], "asc"),
    "lab_work": (["lab_work__number", "lab_work__title", "pk"], "asc"),
    "date": (["scheduled_at", "pk"], "desc"),
    "registration": (
        ["registration_type", "registered_by__last_name", "registered_by__first_name", "pk"],
        "asc",
    ),
    "status": (["current_status", "pk"], "asc"),
    "training_center": (["room__training_center__number", "pk"], "asc"),
    "room": (["room__number", "pk"], "asc"),
}


def order_bookings_queryset(qs, params):
    sort_key = params.get("sort")
    if not sort_key or sort_key not in BOOKING_SORT_FIELDS:
        return qs.order_by("-scheduled_at")

    fields, default_dir = BOOKING_SORT_FIELDS[sort_key]
    direction = params.get("dir", default_dir)
    if direction not in {"asc", "desc"}:
        direction = default_dir

    if direction == "desc":
        order_fields = [f"-{field}" for field in fields]
    else:
        order_fields = list(fields)
    return qs.order_by(*order_fields)


def filter_staff_bookings(qs, params):
    from django.db.models import Q

    if status_val := params.get("status"):
        qs = qs.filter(current_status=status_val)
    if discipline_id := params.get("discipline"):
        qs = qs.filter(discipline_id=discipline_id)
    if date_from := params.get("date_from"):
        qs = qs.filter(scheduled_at__date__gte=date_from)
    if date_to := params.get("date_to"):
        qs = qs.filter(scheduled_at__date__lte=date_to)
    if student_q := params.get("student"):
        qs = qs.filter(_student_search_q(student_q, prefix="student__"))
    return qs


def _student_search_q(query: str, *, prefix: str = ""):
    from django.db.models import Q

    query = query.strip()
    parts = query.split()
    if len(parts) >= 2:
        return (
            Q(**{f"{prefix}last_name__icontains": parts[0], f"{prefix}first_name__icontains": parts[-1]})
            | Q(**{f"{prefix}email__icontains": query})
            | Q(**{f"{prefix}profile__group_name__icontains": query})
            | Q(**{f"{prefix}profile__student_group__name__icontains": query})
        )
    return (
        Q(**{f"{prefix}email__icontains": query})
        | Q(**{f"{prefix}last_name__icontains": query})
        | Q(**{f"{prefix}first_name__icontains": query})
        | Q(**{f"{prefix}profile__group_name__icontains": query})
        | Q(**{f"{prefix}profile__student_group__name__icontains": query})
    )


def search_students_for_staff(query: str, limit: int = 15):
    from django.db.models import Q

    query = (query or "").strip()
    if len(query) < 2:
        return User.objects.none()
    return (
        User.objects.filter(role=UserRole.STUDENT)
        .select_related("profile", "profile__student_group")
        .filter(_student_search_q(query))
        .order_by("last_name", "first_name", "email")[:limit]
    )


def filter_staff_students(qs, params):
    query = (params.get("q") or params.get("student") or "").strip()
    group = (params.get("group") or "").strip()
    if query:
        qs = qs.filter(_student_search_q(query))
    if group:
        qs = qs.filter(
            Q(profile__student_group__name__icontains=group)
            | Q(profile__group_name__icontains=group)
        )
    return qs.distinct()
