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
from apps.bookings.services.session_availability import is_day_open_for_booking
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus
from apps.users.models import User, UserRole


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
        if not skip_student_rules:
            horizon = now + timezone.timedelta(days=settings.BOOKING_HORIZON_DAYS)
            if session.starts_at > horizon:
                raise BookingError(
                    f"Запись доступна только на {settings.BOOKING_HORIZON_DAYS} дней вперёд."
                )
            if not is_day_open_for_booking(session.starts_at.date(), now):
                raise BookingError(
                    f"Запись на этот день откроется в {settings.BOOKING_DAY_OPENS_AT} "
                    f"предыдущего дня."
                )
        if session.starts_at <= now:
            raise BookingError("Нельзя записаться на прошедший слот.")
        if session.status != LabSessionStatus.OPEN:
            raise BookingError("Слот недоступен для записи.")
        if Holiday.objects.filter(date=session.starts_at.date()).exists():
            raise BookingError("Запись в праздничный день недоступна.")

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
        skip_rules = skip_student_rules or manual
        self._validate_booking_window(session, skip_student_rules=skip_rules)
        if not skip_rules:
            self._check_discipline_limit(
                student,
                session.lab_work.discipline_id,
                session.lab_work_id,
            )

        booked_count = session.bookings.filter(current_status=BookingStatus.BOOKED).count()
        if not skip_rules and booked_count >= session.capacity:
            raise BookingError("Нет свободных мест.")

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
            send_mail(
                subject,
                message,
                from_email,
                [booking.student.email],
                fail_silently=True,
            )


def is_staff_user(user: User) -> bool:
    return user.role in {UserRole.LAB_ADMIN, UserRole.TEACHER, UserRole.SYS_ADMIN}
