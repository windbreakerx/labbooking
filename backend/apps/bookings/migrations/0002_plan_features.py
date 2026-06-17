import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0001_initial"),
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticket",
            name="training_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="support_tickets",
                to="scheduling.trainingcenter",
            ),
        ),
    ]
