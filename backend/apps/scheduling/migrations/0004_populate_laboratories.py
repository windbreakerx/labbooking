from django.db import migrations


def populate_laboratories(apps, schema_editor):
    TrainingCenter = apps.get_model("scheduling", "TrainingCenter")
    Laboratory = apps.get_model("scheduling", "Laboratory")
    UserProfile = apps.get_model("users", "UserProfile")
    LabWork = apps.get_model("academics", "LabWork")
    Discipline = apps.get_model("academics", "Discipline")

    for tc in TrainingCenter.objects.all():
        lab_name = tc.name.strip() if tc.name else f"Лаборатория УЦ №{tc.number}"
        lab, _ = Laboratory.objects.get_or_create(
            training_center_id=tc.id,
            name=lab_name,
        )
        for lab_work in LabWork.objects.filter(training_centers=tc):
            lab_work.laboratories.add(lab)
        for discipline in Discipline.objects.filter(training_centers=tc):
            discipline.laboratories.add(lab)
        UserProfile.objects.filter(training_center_id=tc.id, laboratory__isnull=True).update(
            laboratory_id=lab.id
        )


def unpopulate_laboratories(apps, schema_editor):
    Laboratory = apps.get_model("scheduling", "Laboratory")
    Laboratory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0003_laboratory"),
        ("academics", "0006_laboratory"),
        ("users", "0004_laboratory"),
    ]

    operations = [
        migrations.RunPython(populate_laboratories, unpopulate_laboratories),
    ]
