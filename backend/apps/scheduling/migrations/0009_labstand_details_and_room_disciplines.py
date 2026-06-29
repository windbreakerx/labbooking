from django.db import migrations, models


def backfill_room_disciplines(apps, schema_editor):
    Room = apps.get_model("scheduling", "Room")
    Discipline = apps.get_model("academics", "Discipline")
    for room in Room.objects.all():
        discipline_ids = (
            Discipline.objects.filter(lab_works__default_room_id=room.pk)
            .distinct()
            .values_list("pk", flat=True)
        )
        room.disciplines.set(discipline_ids)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0009_labwork_disciplines_m2m"),
        ("scheduling", "0008_backfill_laboratory_faculty"),
    ]

    operations = [
        migrations.AddField(
            model_name="labstand",
            name="is_published",
            field=models.BooleanField(default=True, verbose_name="Опубликован"),
        ),
        migrations.AddField(
            model_name="labstand",
            name="photo",
            field=models.ImageField(blank=True, upload_to="stands/", verbose_name="Фотография"),
        ),
        migrations.AddField(
            model_name="room",
            name="disciplines",
            field=models.ManyToManyField(
                blank=True,
                related_name="rooms",
                to="academics.discipline",
                verbose_name="Дисциплины",
            ),
        ),
        migrations.RunPython(backfill_room_disciplines, migrations.RunPython.noop),
    ]
