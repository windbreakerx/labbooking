import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
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
    is_pair_time_for_booking,
    is_weekday_for_booking,
    booking_date_window,
)
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus
from apps.users.models import User, UserRole

logger = logging.getLogger(__name__)


class BookingError(Exception):
    pass


ACTIVE_STATUSES = {BookingStatus.BOOKED}
BLOCKING_VISITED_LAB = {BookingStatus.VISITED}


class BookingService:
    def __init__(self, actor: User | None = None, ip_address: str | None = None):
        self.actor = actor
        self.ip_address = ip_address

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

    def _room_overlap_booked(self, session: LabSession) -> int:
        return Booking.objects.filter(
            current_status=BookingStatus.BOOKED,
            lab_session__room_id=session.room_id,
            lab_session__starts_at__lt=session.ends_at,
            lab_session__ends_at__gt=session.starts_at,
        ).count()

    def _lock_overlapping_room_sessions(self, session: LabSession):
        """
        Блокирует все пересекающиеся слоты аудитории в рамках транзакции.
        Это предотвращает гонку при одновременной записи на последние места
        в параллельных ЛР одной аудитории.
        """
        overlapping_qs = LabSession.objects.select_for_update().filter(
            room_id=session.room_id,
            starts_at__lt=session.ends_at,
            ends_at__gt=session.starts_at,
        )
        # Принудительно выполняем SELECT ... FOR UPDATE.
        list(overlapping_qs.values_list("id", flat=True))

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

    @transaction.atomic
    def create_booking(
        self,
        student: User,
        session_id: int,
        manual: bool = False,
        skip_student_rules: bool = False,
    ) -> Booking:
        session = (
            LabSession.objects.select_for_update()
            .select_related("lab_work", "lab_work__discipline", "room")
            .get(pk=session_id)
        )
        self._lock_overlapping_room_sessions(session)
        skip_rules = skip_student_rules or manual
        self._validate_booking_window(session, skip_student_rules=skip_rules)
        if not skip_rules and student.role == UserRole.STUDENT:
            from apps.academics.querysets import student_can_access_lab_work

            if not student_can_access_lab_work(student, session.lab_work_id):
                raise BookingError("Лабораторная работа недоступна для вашей группы.")
        if not skip_rules:
            self._check_discipline_limit(
                student,
                session.lab_work.discipline_id,
                session.lab_work_id,
            )

        booked_count = session.bookings.filter(current_status=BookingStatus.BOOKED).count()
        if not skip_rules and booked_count >= session.capacity:
            raise BookingError("Нет свободных мест.")
        room_overlap_booked = self._room_overlap_booked(session)
        if room_overlap_booked >= session.room.capacity:
            raise BookingError(
                f"Аудитория {session.room.number} заполнена на это время. Выберите другую пару."
            )

        booking = Booking.objects.create(
            student=student,
            lab_session=session,
            lab_work=session.lab_work,
            discipline=session.lab_work.discipline,
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
        session = LabSession.objects.select_for_update().get(pk=session_id)
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


def staff_lab_filter(qs, user, *, training_center_lookup: str = "room__training_center"):
    """Ограничивает queryset сотрудника своей лабораторией (SYS_ADMIN видит всё)."""
    if user.role == UserRole.SYS_ADMIN:
        return qs
    tc = getattr(user.profile, "training_center", None)
    if not tc:
        return qs.none()
    lookup_value = tc.pk if training_center_lookup in {"pk", "id"} else tc
    return qs.filter(**{training_center_lookup: lookup_value})


def staff_can_access_scoped_object(user: User, qs, *, training_center_lookup: str = "room__training_center") -> bool:
    return staff_lab_filter(qs, user, training_center_lookup=training_center_lookup).exists()


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
