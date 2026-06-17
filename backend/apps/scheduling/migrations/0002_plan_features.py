import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0002_plan_features"),
        ("scheduling", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LabStand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=256, verbose_name="Наименование")),
                ("inventory_number", models.CharField(max_length=64, verbose_name="Инвентарный номер")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stands",
                        to="scheduling.room",
                    ),
                ),
                (
                    "training_center",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stands",
                        to="scheduling.trainingcenter",
                    ),
                ),
            ],
            options={
                "verbose_name": "Лабораторный стенд",
                "verbose_name_plural": "Лабораторные стенды",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ScheduleEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_parity", models.CharField(
                    choices=[("ODD", "Нечётная"), ("EVEN", "Чётная"), ("BOTH", "Каждую неделю")],
                    default="BOTH",
                    max_length=8,
                )),
                ("weekday", models.PositiveSmallIntegerField(verbose_name="День недели (0=Пн)")),
                ("start_time", models.TimeField(verbose_name="Время начала")),
                ("duration_minutes", models.PositiveIntegerField(default=90, verbose_name="Длительность (мин)")),
                ("capacity", models.PositiveIntegerField(default=30, verbose_name="Мест")),
                ("is_active", models.BooleanField(default=True)),
                (
                    "lab_work",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedule_entries",
                        to="academics.labwork",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="schedule_entries",
                        to="scheduling.room",
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedule_entries",
                        to="academics.semester",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="schedule_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Запись расписания",
                "verbose_name_plural": "Расписание",
                "ordering": ["weekday", "start_time"],
            },
        ),
    ]
