from django.db import migrations, models


def backfill_laboratory_faculty(apps, schema_editor):
    Faculty = apps.get_model("academics", "Faculty")
    Laboratory = apps.get_model("scheduling", "Laboratory")

    ngf = Faculty.objects.filter(code="НГФ").first()
    if ngf is None:
        return

    Laboratory.objects.filter(faculty__isnull=True).update(faculty_id=ngf.id)
    Laboratory.objects.filter(name__icontains="комплексн").update(lab_type="COMPLEX")


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0011_faculty"),
        ("scheduling", "0006_room_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="laboratory",
            name="faculty",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="laboratories",
                to="academics.faculty",
                verbose_name="Факультет",
            ),
        ),
        migrations.AddField(
            model_name="laboratory",
            name="lab_type",
            field=models.CharField(
                choices=[
                    ("REGULAR", "Кафедральная"),
                    ("INTERDEPT", "Межкафедральная"),
                    ("COMPLEX", "Комплексная"),
                ],
                default="REGULAR",
                max_length=16,
                verbose_name="Тип лаборатории",
            ),
        ),
        migrations.RunPython(backfill_laboratory_faculty, migrations.RunPython.noop),
    ]
