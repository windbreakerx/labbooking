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
    is_published = models.BooleanField("Опубликовано", default=True)

    class Meta:
        verbose_name = "Лабораторная работа"
        verbose_name_plural = "Лабораторные работы"
        ordering = ["discipline", "number"]
        unique_together = [("discipline", "number")]

    def __str__(self):
        return f"{self.discipline.title} — ЛР {self.number}: {self.title}"
