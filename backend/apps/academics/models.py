from django.core.validators import FileExtensionValidator
from django.db import models


class Semester(models.Model):
    name = models.CharField("Название", max_length=128)
    start_date = models.DateField("Дата начала")
    end_date = models.DateField("Дата окончания")
    is_active = models.BooleanField("Активный", default=False)

    class Meta:
        verbose_name = "Семестр"
        verbose_name_plural = "Семестры"
        ordering = ["-start_date"]

    def __str__(self):
        return self.name


class StudentGroup(models.Model):
    name = models.CharField("Группа", max_length=64, unique=True)
    faculty = models.CharField("Факультет", max_length=128, blank=True)
    dekanat_id = models.CharField("ID в Деканате", max_length=64, blank=True)
    disciplines = models.ManyToManyField(
        "Discipline",
        blank=True,
        related_name="student_groups",
        verbose_name="Дисциплины учебного плана",
    )
    lab_works = models.ManyToManyField(
        "LabWork",
        blank=True,
        related_name="student_groups",
        verbose_name="Лабораторные работы учебного плана",
    )

    class Meta:
        verbose_name = "Учебная группа"
        verbose_name_plural = "Учебные группы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Discipline(models.Model):
    code = models.CharField("Код", max_length=32, blank=True)
    title = models.CharField("Название", max_length=256)
    description = models.TextField("Описание", blank=True)
    is_published = models.BooleanField("Опубликовано", default=True)
    dekanat_id = models.CharField("ID в Деканате", max_length=64, blank=True)
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="disciplines",
        null=True,
        blank=True,
    )
    training_centers = models.ManyToManyField(
        "scheduling.TrainingCenter",
        blank=True,
        related_name="disciplines",
        verbose_name="Лаборатории",
    )

    class Meta:
        verbose_name = "Дисциплина"
        verbose_name_plural = "Дисциплины"
        ordering = ["title"]

    def __str__(self):
        return self.title


class LabWork(models.Model):
    discipline = models.ForeignKey(
        Discipline,
        on_delete=models.CASCADE,
        related_name="lab_works",
    )
    number = models.PositiveIntegerField("Номер", default=1)
    title = models.CharField("Название", max_length=256)
    description = models.TextField("Описание", blank=True)
    duration_minutes = models.PositiveIntegerField("Длительность (мин)", default=90)
    capacity = models.PositiveIntegerField("Макс. мест", default=30)
    is_published = models.BooleanField("Опубликовано", default=True)
    methodics_file = models.FileField(
        "Методичка (PDF)",
        upload_to="methodics/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )
    training_centers = models.ManyToManyField(
        "scheduling.TrainingCenter",
        blank=True,
        related_name="lab_works",
        verbose_name="Лаборатории",
    )
    default_room = models.ForeignKey(
        "scheduling.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_lab_works",
        verbose_name="Аудитория по умолчанию",
    )

    class Meta:
        verbose_name = "Лабораторная работа"
        verbose_name_plural = "Лабораторные работы"
        ordering = ["discipline", "number"]
        unique_together = [("discipline", "number")]

    def __str__(self):
        return f"{self.discipline.title} — ЛР {self.number}: {self.title}"
