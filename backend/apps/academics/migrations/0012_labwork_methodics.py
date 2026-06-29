from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


def migrate_methodics_files(apps, schema_editor):
    LabWork = apps.get_model("academics", "LabWork")
    LabWorkMethodics = apps.get_model("academics", "LabWorkMethodics")
    for lab_work in LabWork.objects.all():
        file_name = getattr(lab_work, "methodics_file", "") or ""
        if not file_name:
            continue
        LabWorkMethodics.objects.create(
            lab_work_id=lab_work.pk,
            file=file_name,
            title="",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0011_faculty"),
    ]

    operations = [
        migrations.CreateModel(
            name="LabWorkMethodics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "file",
                    models.FileField(
                        upload_to="methodics/",
                        validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["pdf"])],
                        verbose_name="PDF",
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=256, verbose_name="Название")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружено")),
                (
                    "lab_work",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="methodics_files",
                        to="academics.labwork",
                        verbose_name="Лабораторная работа",
                    ),
                ),
            ],
            options={
                "verbose_name": "Методичка",
                "verbose_name_plural": "Методички",
                "ordering": ["uploaded_at", "pk"],
            },
        ),
        migrations.RunPython(migrate_methodics_files, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="labwork",
            name="methodics_file",
        ),
    ]
