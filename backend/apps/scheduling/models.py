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
        if self.name:
            return f"УЦ №{self.number} — {self.name}"
        return f"УЦ №{self.number}"


class Laboratory(models.Model):
    training_center = models.ForeignKey(
        TrainingCenter,
        on_delete=models.CASCADE,
        related_name="laboratories",
        verbose_name="Учебный центр",
    )
    name = models.CharField("Название", max_length=256)
    short_name = models.CharField("Краткое название", max_length=64, blank=True)

    class Meta:
        verbose_name = "Лаборатория"
        verbose_name_plural = "Лаборатории"
        ordering = ["training_center", "name"]
        unique_together = [("training_center", "name")]

    def __str__(self):
        return self.name


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
        from apps.bookings.models import Booking, BookingStatus

        session_booked = self.booked_count
        room_overlap_booked = Booking.objects.filter(
            current_status=BookingStatus.BOOKED,
            lab_session__room_id=self.room_id,
            lab_session__starts_at__lt=self.ends_at,
            lab_session__ends_at__gt=self.starts_at,
        ).count()
        return max(
            0,
            min(
                self.capacity - session_booked,
                self.room.capacity - room_overlap_booked,
            ),
        )


class Holiday(models.Model):
    date = models.DateField("Дата", unique=True)
    name = models.CharField("Название", max_length=128, blank=True)

    class Meta:
        verbose_name = "Праздничный день"
        verbose_name_plural = "Праздничные дни"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}".strip()


class WeekParity(models.TextChoices):
    ODD = "ODD", "Нечётная"
    EVEN = "EVEN", "Чётная"
    BOTH = "BOTH", "Каждую неделю"


class LabStand(models.Model):
    name = models.CharField("Наименование", max_length=256)
    inventory_number = models.CharField("Инвентарный номер", max_length=64)
    training_center = models.ForeignKey(
        TrainingCenter,
        on_delete=models.CASCADE,
        related_name="stands",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="stands",
    )
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Лабораторный стенд"
        verbose_name_plural = "Лабораторные стенды"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.inventory_number})"


class ScheduleEntry(models.Model):
    lab_work = models.ForeignKey(
        LabWork,
        on_delete=models.CASCADE,
        related_name="schedule_entries",
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="schedule_entries")
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="schedule_entries",
    )
    week_parity = models.CharField(
        max_length=8,
        choices=WeekParity.choices,
        default=WeekParity.BOTH,
    )
    weekday = models.PositiveSmallIntegerField("День недели (0=Пн)")
    start_time = models.TimeField("Время начала")
    duration_minutes = models.PositiveIntegerField("Длительность (мин)", default=90)
    capacity = models.PositiveIntegerField("Мест", default=30)
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_entries",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Запись расписания"
        verbose_name_plural = "Расписание"
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.lab_work} — день {self.weekday} {self.start_time}"
