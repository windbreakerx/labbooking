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
    atomic = False

    dependencies = [
        ("scheduling", "0007_laboratory_faculty"),
    ]

    operations = [
        migrations.RunPython(backfill_laboratory_faculty, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="laboratory",
            index=models.Index(fields=["faculty"], name="scheduling_laboratory_faculty_id_idx"),
        ),
    ]
