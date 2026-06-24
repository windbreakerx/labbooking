from django.db import migrations, models

ALLOWED_DURATIONS = (30, 45, 60, 90)


def normalize_lab_work_durations(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE academics_labwork
            SET duration_minutes = CASE
                WHEN duration_minutes <= 37 THEN 30
                WHEN duration_minutes <= 52 THEN 45
                WHEN duration_minutes <= 75 THEN 60
                ELSE 90
            END
            WHERE duration_minutes NOT IN (30, 45, 60, 90)
            """
        )


def backfill_primary_stand(apps, schema_editor):
    LabWork = apps.get_model("academics", "LabWork")
    LabStand = apps.get_model("scheduling", "LabStand")
    Room = apps.get_model("scheduling", "Room")

    for lab_work in LabWork.objects.exclude(default_room_id__isnull=True):
        room = Room.objects.filter(pk=lab_work.default_room_id).first()
        if room is None:
            continue
        candidates = LabStand.objects.filter(
            training_center_id=room.training_center_id,
            room_id=room.id,
        )
        stand = candidates.filter(description__icontains=lab_work.title[:64]).first()
        if stand is None:
            stand = candidates.filter(inventory_number=f"LR-{lab_work.id:05d}").first()
        if stand is None:
            stand = candidates.first()
        if stand is not None:
            LabWork.objects.filter(pk=lab_work.pk).update(primary_stand_id=stand.id)


class Migration(migrations.Migration):
    atomic = False

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
        migrations.RunPython(normalize_lab_work_durations, migrations.RunPython.noop),
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
                check=models.Q(duration_minutes__in=ALLOWED_DURATIONS),
                name="academics_labwork_allowed_duration",
            ),
        ),
        migrations.RunPython(backfill_primary_stand, migrations.RunPython.noop),
    ]
