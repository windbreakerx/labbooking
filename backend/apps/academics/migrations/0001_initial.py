import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Semester",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, verbose_name="Название")),
                ("start_date", models.DateField(verbose_name="Дата начала")),
                ("end_date", models.DateField(verbose_name="Дата окончания")),
                ("is_active", models.BooleanField(default=False, verbose_name="Активный")),
            ],
            options={
                "verbose_name": "Семестр",
                "verbose_name_plural": "Семестры",
                "ordering": ["-start_date"],
            },
        ),
        migrations.CreateModel(
            name="Discipline",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, max_length=32, verbose_name="Код")),
                ("title", models.CharField(max_length=256, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("is_published", models.BooleanField(default=True, verbose_name="Опубликовано")),
                ("dekanat_id", models.CharField(blank=True, max_length=64, verbose_name="ID в Деканате")),
                ("semester", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="disciplines", to="academics.semester")),
            ],
            options={
                "verbose_name": "Дисциплина",
                "verbose_name_plural": "Дисциплины",
                "ordering": ["title"],
            },
        ),
        migrations.CreateModel(
            name="LabWork",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField(default=1, verbose_name="Номер")),
                ("title", models.CharField(max_length=256, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("duration_minutes", models.PositiveIntegerField(default=90, verbose_name="Длительность (мин)")),
                ("is_published", models.BooleanField(default=True, verbose_name="Опубликовано")),
                ("discipline", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lab_works", to="academics.discipline")),
            ],
            options={
                "verbose_name": "Лабораторная работа",
                "verbose_name_plural": "Лабораторные работы",
                "ordering": ["discipline", "number"],
                "unique_together": {("discipline", "number")},
            },
        ),
    ]
