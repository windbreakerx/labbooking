import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_access_scope"),
        ("scheduling", "0002_plan_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="labwork",
            name="default_room",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="default_lab_works",
                to="scheduling.room",
                verbose_name="Аудитория по умолчанию",
            ),
        ),
    ]
