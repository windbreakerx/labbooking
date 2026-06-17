from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="labwork",
            name="methodics_file",
            field=models.FileField(
                blank=True,
                upload_to="methodics/",
                validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["pdf"])],
                verbose_name="Методичка (PDF)",
            ),
        ),
    ]
