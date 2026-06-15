import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("academics", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TrainingCenter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField(unique=True, verbose_name="УЦ №")),
                ("name", models.CharField(blank=True, max_length=128, verbose_name="Название")),
            ],
            options={
                "verbose_name": "Учебный центр",
                "verbose_name_plural": "Учебные центры",
            },
        ),
        migrations.CreateModel(
            name="Holiday",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True, verbose_name="Дата")),
                ("name", models.CharField(blank=True, max_length=128, verbose_name="Название")),
            ],
            options={
                "verbose_name": "Праздничный день",
                "verbose_name_plural": "Праздничные дни",
                "ordering": ["date"],
            },
        ),
        migrations.CreateModel(
            name="Room",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(max_length=32, verbose_name="Аудитория №")),
                ("capacity", models.PositiveIntegerField(default=30, verbose_name="Вместимость")),
                ("training_center", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rooms", to="scheduling.trainingcenter")),
            ],
            options={
                "verbose_name": "Аудитория",
                "verbose_name_plural": "Аудитории",
                "unique_together": {("training_center", "number")},
            },
        ),
        migrations.CreateModel(
            name="LabSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_at", models.DateTimeField(verbose_name="Начало")),
                ("ends_at", models.DateTimeField(verbose_name="Окончание")),
                ("capacity", models.PositiveIntegerField(verbose_name="Мест")),
                ("status", models.CharField(choices=[("DRAFT", "Черновик"), ("OPEN", "Открыта"), ("CLOSED", "Закрыта"), ("CANCELLED", "Отменена")], default="OPEN", max_length=16)),
                ("lab_work", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="academics.labwork")),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="scheduling.room")),
                ("semester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="academics.semester")),
                ("teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="taught_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Слот лабораторной",
                "verbose_name_plural": "Слоты лабораторных",
                "ordering": ["starts_at"],
            },
        ),
        migrations.AddIndex(
            model_name="labsession",
            index=models.Index(fields=["starts_at", "status"], name="scheduling__starts__a5f2c1_idx"),
        ),
        migrations.AddIndex(
            model_name="labsession",
            index=models.Index(fields=["lab_work", "starts_at"], name="scheduling__lab_wor_91ab42_idx"),
        ),
    ]
