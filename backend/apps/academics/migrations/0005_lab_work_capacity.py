from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0004_labwork_default_room"),
    ]

    operations = [
        migrations.AddField(
            model_name="labwork",
            name="capacity",
            field=models.PositiveIntegerField(default=30, verbose_name="Макс. мест"),
        ),
    ]
