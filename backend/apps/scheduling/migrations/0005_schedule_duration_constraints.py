from django.db import migrations, models

ALLOWED_DURATIONS = (30, 45, 60, 90)


def normalize_schedule_entry_durations(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE scheduling_scheduleentry
            SET duration_minutes = CASE
                WHEN duration_minutes <= 37 THEN 30
                WHEN duration_minutes <= 52 THEN 45
                WHEN duration_minutes <= 75 THEN 60
                ELSE 90
            END
            WHERE duration_minutes NOT IN (30, 45, 60, 90)
            """
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("scheduling", "0004_populate_laboratories"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scheduleentry",
            name="duration_minutes",
            field=models.PositiveIntegerField(
                choices=[(30, "30 мин"), (45, "45 мин"), (60, "60 мин"), (90, "90 мин")],
                default=90,
                verbose_name="Длительность (мин)",
            ),
        ),
        migrations.RunPython(normalize_schedule_entry_durations, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="scheduleentry",
            constraint=models.CheckConstraint(
                check=models.Q(duration_minutes__in=ALLOWED_DURATIONS),
                name="scheduling_scheduleentry_allowed_duration",
            ),
        ),
    ]
