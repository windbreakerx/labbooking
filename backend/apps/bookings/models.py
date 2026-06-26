from django.db import models

from apps.academics.models import Discipline, LabWork
from apps.scheduling.models import LabSession, Room, TrainingCenter
from apps.users.models import User


class BookingStatus(models.TextChoices):
    BOOKED = "BOOKED", "Записан"
    NO_SHOW = "NO_SHOW", "Неявка"
    CANCELLED = "CANCELLED", "Отменил запись"
    REACCESS = "REACCESS", "Повторный доступ"
    VISITED = "VISITED", "Посетил"


class RegistrationType(models.TextChoices):
    AUTO = "AUTO", "Автоматическая"
    MANUAL = "MANUAL", "Не автоматическая"


class Booking(models.Model):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    lab_session = models.ForeignKey(
        LabSession,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    lab_work = models.ForeignKey(LabWork, on_delete=models.CASCADE, related_name="bookings")
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    scheduled_at = models.DateTimeField("Дата и время ЛР")
    current_status = models.CharField(
        max_length=16,
        choices=BookingStatus.choices,
        default=BookingStatus.BOOKED,
    )
    registration_type = models.CharField(
        max_length=16,
        choices=RegistrationType.choices,
        default=RegistrationType.AUTO,
    )
    registered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_bookings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["-scheduled_at"]
        indexes = [
            models.Index(fields=["student", "discipline", "current_status"]),
            models.Index(fields=["scheduled_at", "current_status"]),
        ]

    def __str__(self):
        return f"{self.student.email} — {self.lab_work} ({self.current_status})"


class BookingStatusHistory(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    status = models.CharField(max_length=16, choices=BookingStatus.choices)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "История статуса"
        verbose_name_plural = "История статусов"
        ordering = ["changed_at"]

    def __str__(self):
        return f"{self.booking_id} → {self.status}"


class WaitlistEntry(models.Model):
    lab_session = models.ForeignKey(
        LabSession,
        on_delete=models.CASCADE,
        related_name="waitlist",
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="waitlist_entries")
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Очередь"
        verbose_name_plural = "Очередь"
        unique_together = [("lab_session", "student")]
        ordering = ["position"]

    def __str__(self):
        return f"#{self.position} {self.student.email}"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.PositiveIntegerField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Аудит"
        verbose_name_plural = "Аудит"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.entity_type}:{self.entity_id}"


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Открыт"
        ANSWERED = "ANSWERED", "Закрыт"
        CLOSED = "CLOSED", "Закрыт"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="support_tickets")
    training_center = models.ForeignKey(
        TrainingCenter,
        on_delete=models.PROTECT,
        related_name="support_tickets",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=256)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Обращение"
        verbose_name_plural = "Обращения"
        ordering = ["-created_at"]

    @property
    def is_response_overdue(self) -> bool:
        from apps.bookings.services.support import is_support_ticket_overdue

        return is_support_ticket_overdue(self)


class SupportMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
