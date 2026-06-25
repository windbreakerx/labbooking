from collections import Counter, defaultdict

from django.db import migrations, models


def migrate_discipline_to_m2m(apps, schema_editor):
    LabWork = apps.get_model("academics", "LabWork")
    for lab_work in LabWork.objects.exclude(discipline_id__isnull=True).iterator():
        lab_work.disciplines.add(lab_work.discipline_id)


def _lab_signature(lab_work) -> tuple:
    lab_ids = tuple(sorted(lab_work.laboratories.values_list("pk", flat=True)))
    return (
        lab_work.title.strip().lower(),
        lab_work.default_room_id,
        lab_work.primary_stand_id,
        lab_ids,
    )


def _activity_score(lab_work, Booking, LabSession, StudentGroup) -> int:
    return (
        LabSession.objects.filter(lab_work_id=lab_work.pk).count()
        + Booking.objects.filter(lab_work_id=lab_work.pk).count()
        + StudentGroup.objects.filter(lab_works=lab_work.pk).count()
    )


def merge_duplicate_lab_works(apps, schema_editor):
    LabWork = apps.get_model("academics", "LabWork")
    Booking = apps.get_model("bookings", "Booking")
    LabSession = apps.get_model("scheduling", "LabSession")
    ScheduleEntry = apps.get_model("scheduling", "ScheduleEntry")
    StudentGroup = apps.get_model("academics", "StudentGroup")

    groups: dict[tuple, list] = defaultdict(list)
    for lab_work in LabWork.objects.prefetch_related("laboratories").iterator():
        groups[_lab_signature(lab_work)].append(lab_work)

    for duplicates in groups.values():
        if len(duplicates) < 2:
            continue
        canonical = max(
            duplicates,
            key=lambda lw: _activity_score(lw, Booking, LabSession, StudentGroup),
        )
        duplicate_ids = [lw.pk for lw in duplicates if lw.pk != canonical.pk]
        if not duplicate_ids:
            continue

        durations = [lw.duration_minutes for lw in duplicates]
        canonical.duration_minutes = Counter(durations).most_common(1)[0][0]
        canonical.save(update_fields=["duration_minutes"])

        for duplicate in duplicates:
            if duplicate.pk == canonical.pk:
                continue
            canonical.disciplines.add(*duplicate.disciplines.values_list("pk", flat=True))
            canonical.student_groups.add(*duplicate.student_groups.values_list("pk", flat=True))
            canonical.laboratories.add(*duplicate.laboratories.values_list("pk", flat=True))
            canonical.training_centers.add(*duplicate.training_centers.values_list("pk", flat=True))

            LabSession.objects.filter(lab_work_id=duplicate.pk).update(lab_work_id=canonical.pk)
            Booking.objects.filter(lab_work_id=duplicate.pk).update(lab_work_id=canonical.pk)
            ScheduleEntry.objects.filter(lab_work_id=duplicate.pk).update(lab_work_id=canonical.pk)

        LabWork.objects.filter(pk__in=duplicate_ids).delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("academics", "0008_department"),
        ("bookings", "0001_initial"),
        ("scheduling", "0005_schedule_duration_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="labwork",
            name="disciplines",
            field=models.ManyToManyField(
                related_name="lab_works",
                to="academics.discipline",
                verbose_name="Дисциплины",
            ),
        ),
        migrations.RunPython(migrate_discipline_to_m2m, migrations.RunPython.noop),
        migrations.RunPython(merge_duplicate_lab_works, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="labwork",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="labwork",
            name="discipline",
        ),
        migrations.AlterModelOptions(
            name="labwork",
            options={
                "ordering": ["number", "title"],
                "verbose_name": "Лабораторная работа",
                "verbose_name_plural": "Лабораторные работы",
            },
        ),
    ]
