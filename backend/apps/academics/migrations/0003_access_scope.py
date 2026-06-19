import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0002_plan_features"),
        ("scheduling", "0002_plan_features"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, unique=True, verbose_name="Группа")),
                ("faculty", models.CharField(blank=True, max_length=128, verbose_name="Факультет")),
                ("dekanat_id", models.CharField(blank=True, max_length=64, verbose_name="ID в Деканате")),
            ],
            options={
                "verbose_name": "Учебная группа",
                "verbose_name_plural": "Учебные группы",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="discipline",
            name="training_centers",
            field=models.ManyToManyField(
                blank=True,
                related_name="disciplines",
                to="scheduling.trainingcenter",
                verbose_name="Лаборатории",
            ),
        ),
        migrations.AddField(
            model_name="labwork",
            name="training_centers",
            field=models.ManyToManyField(
                blank=True,
                related_name="lab_works",
                to="scheduling.trainingcenter",
                verbose_name="Лаборатории",
            ),
        ),
        migrations.AddField(
            model_name="studentgroup",
            name="disciplines",
            field=models.ManyToManyField(
                blank=True,
                related_name="student_groups",
                to="academics.discipline",
                verbose_name="Дисциплины учебного плана",
            ),
        ),
        migrations.AddField(
            model_name="studentgroup",
            name="lab_works",
            field=models.ManyToManyField(
                blank=True,
                related_name="student_groups",
                to="academics.labwork",
                verbose_name="Лабораторные работы учебного плана",
            ),
        ),
    ]
