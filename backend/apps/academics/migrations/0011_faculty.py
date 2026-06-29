from django.db import migrations, models


NGF_FACULTY = {
    "code": "НГФ",
    "title": "Нефтегазовый факультет",
    "ordering": 0,
}


def populate_faculty_and_links(apps, schema_editor):
    Faculty = apps.get_model("academics", "Faculty")
    Department = apps.get_model("academics", "Department")

    ngf, _ = Faculty.objects.get_or_create(
        code=NGF_FACULTY["code"],
        defaults={
            "title": NGF_FACULTY["title"],
            "ordering": NGF_FACULTY["ordering"],
        },
    )
    Department.objects.filter(faculty__isnull=True).update(faculty_id=ngf.id)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0010_labwork_code_and_short_codes"),
    ]

    operations = [
        migrations.CreateModel(
            name="Faculty",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=16, unique=True, verbose_name="Код")),
                ("title", models.CharField(max_length=256, verbose_name="Название")),
                ("ordering", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Факультет",
                "verbose_name_plural": "Факультеты",
                "ordering": ["ordering", "title"],
            },
        ),
        migrations.AddField(
            model_name="department",
            name="faculty",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="departments",
                to="academics.faculty",
                verbose_name="Факультет",
            ),
        ),
        migrations.AddField(
            model_name="studentgroup",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="student_groups",
                to="academics.department",
                verbose_name="Кафедра",
            ),
        ),
        migrations.RunPython(populate_faculty_and_links, migrations.RunPython.noop),
    ]
