from django.db import migrations, models


class Migration(migrations.Migration):
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
        migrations.AddConstraint(
            model_name="scheduleentry",
            constraint=models.CheckConstraint(
                check=models.Q(duration_minutes__in=(30, 45, 60, 90)),
                name="scheduling_scheduleentry_allowed_duration",
            ),
        ),
    ]
