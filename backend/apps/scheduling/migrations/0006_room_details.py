from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0005_schedule_duration_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="laboratory",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="rooms",
                to="scheduling.laboratory",
                verbose_name="Лаборатория",
            ),
        ),
        migrations.AddField(
            model_name="room",
            name="name",
            field=models.CharField(blank=True, max_length=256, verbose_name="Название"),
        ),
        migrations.AddField(
            model_name="room",
            name="photo",
            field=models.ImageField(blank=True, upload_to="rooms/", verbose_name="Фотография"),
        ),
    ]
