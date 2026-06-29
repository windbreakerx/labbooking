from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

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
                db_index=False,
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
                db_default="REGULAR",
                default="REGULAR",
                max_length=16,
                verbose_name="Тип лаборатории",
            ),
        ),
    ]
