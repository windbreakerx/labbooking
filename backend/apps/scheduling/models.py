from django.db import models

from apps.academics.models import LabWork, Semester
from apps.users.models import User


class TrainingCenter(models.Model):
    number = models.PositiveIntegerField("УЦ №", unique=True)
    name = models.CharField("Название", max_length=128, blank=True)

    class Meta:
        verbose_name = "Учебный центр"
        verbose_name_plural = "Учебные центры"

    def __str__(self):
        return f"УЦ №{self.number}"


class Room(models.Model):
    training_center = models.ForeignKey(
        TrainingCenter,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    number = models.CharField("Аудитория №", max_length=32)
    capacity = models.PositiveIntegerField("Вместимость", default=30)

    class Meta:
        verbose_name = "Аудитория"
        verbose_name_plural = "Аудитории"
        unique_together = [("training_center", "number")]

    def __str__(self):
        return f"УЦ №{self.training_center.number}, ауд. {self.number}"


class LabSessionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Черновик"
    OPEN = "OPEN", "Открыта"
    CLOSED = "CLOSED", "Закрыта"
    CANCELLED = "CANCELLED", "Отменена"


class LabSession(models.Model):
    lab_work = models.ForeignKey(
        LabWork,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="sessions")
    semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_sessions",
    )
    starts_at = models.DateTimeField("Начало")
    ends_at = models.DateTimeField("Окончание")
    capacity = models.PositiveIntegerField("Мест")
    status = models.CharField(
        max_length=16,
        choices=LabSessionStatus.choices,
        default=LabSessionStatus.OPEN,
    )

    class Meta:
        verbose_name = "Слот лабораторной"
        verbose_name_plural = "Слоты лабораторных"
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["starts_at", "status"]),
            models.Index(fields=["lab_work", "starts_at"]),
        ]

    def __str__(self):
        return f"{self.lab_work} — {self.starts_at:%d.%m.%Y %H:%M}"

    @property
    def booked_count(self):
        from apps.bookings.models import Booking, BookingStatus

        return self.bookings.filter(current_status=BookingStatus.BOOKED).count()

    @property
    def available_seats(self):
        return max(0, self.capacity - self.booked_count)


class Holiday(models.Model):
    date = models.DateField("Дата", unique=True)
    name = models.CharField("Название", max_length=128, blank=True)

    class Meta:
        verbose_name = "Праздничный день"
        verbose_name_plural = "Праздничные дни"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}".strip()
