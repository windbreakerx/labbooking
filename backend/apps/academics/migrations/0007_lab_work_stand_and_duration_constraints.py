from django.db import migrations, models


def backfill_primary_stand(apps, schema_editor):
    LabWork = apps.get_model("academics", "LabWork")
    LabStand = apps.get_model("scheduling", "LabStand")

    for lab_work in LabWork.objects.exclude(default_room__isnull=True):
        candidates = LabStand.objects.filter(
            training_center_id=lab_work.default_room.training_center_id,
            room_id=lab_work.default_room_id,
        )
        stand = candidates.filter(description__icontains=lab_work.title[:64]).first()
        if stand is None:
            stand = candidates.filter(inventory_number=f"LR-{lab_work.id:05d}").first()
        if stand is None:
            stand = candidates.first()
        if stand is not None:
            lab_work.primary_stand_id = stand.id
            lab_work.save(update_fields=["primary_stand"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0006_laboratory"),
        ("scheduling", "0004_populate_laboratories"),
    ]

    operations = [
        migrations.AlterField(
            model_name="labwork",
            name="duration_minutes",
            field=models.PositiveIntegerField(
                choices=[(30, "30 мин"), (45, "45 мин"), (60, "60 мин"), (90, "90 мин")],
                default=90,
                verbose_name="Длительность (мин)",
            ),
        ),
        migrations.AddField(
            model_name="labwork",
            name="primary_stand",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="primary_for_lab_works",
                to="scheduling.labstand",
                verbose_name="Основной стенд",
            ),
        ),
        migrations.AddConstraint(
            model_name="labwork",
            constraint=models.CheckConstraint(
                check=models.Q(duration_minutes__in=(30, 45, 60, 90)),
                name="academics_labwork_allowed_duration",
            ),
        ),
        migrations.RunPython(backfill_primary_stand, migrations.RunPython.noop),
    ]
