from django.db import models

from apps.academics.models import (
    ALLOWED_LAB_DURATIONS,
    ALLOWED_LAB_DURATIONS_CHOICES,
    LabWork,
    Semester,
)
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
    name = models.CharField("Название", max_length=256, blank=True)
    photo = models.ImageField("Фотография", upload_to="rooms/", blank=True)
    capacity = models.PositiveIntegerField("Вместимость", default=30)
    laboratory = models.ForeignKey(
        Laboratory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rooms",
        verbose_name="Лаборатория",
    )

    class Meta:
        verbose_name = "Аудитория"
        verbose_name_plural = "Аудитории"
        unique_together = [("training_center", "number")]

    def __str__(self):
        if self.name:
            return f"ауд. {self.number} — {self.name}"
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

    def is_stand_blocked_by_other_lab_work(self) -> bool:
        stand_id = self.lab_work.primary_stand_id
        if not stand_id:
            return False
        from apps.bookings.models import Booking, BookingStatus

        return (
            Booking.objects.filter(
                current_status=BookingStatus.BOOKED,
                lab_session__lab_work__primary_stand_id=stand_id,
                lab_session__starts_at__lt=self.ends_at,
                lab_session__ends_at__gt=self.starts_at,
            )
            .exclude(lab_session__lab_work_id=self.lab_work_id)
            .exists()
        )

    @property
    def available_seats(self):
        from apps.bookings.services.session_availability import session_available_seats

        return session_available_seats(self)


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
    duration_minutes = models.PositiveIntegerField(
        "Длительность (мин)",
        default=90,
        choices=ALLOWED_LAB_DURATIONS_CHOICES,
    )
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
        constraints = [
            models.CheckConstraint(
                check=models.Q(duration_minutes__in=ALLOWED_LAB_DURATIONS),
                name="scheduling_scheduleentry_allowed_duration",
            )
        ]

    def __str__(self):
        return f"{self.lab_work} — день {self.weekday} {self.start_time}"
