import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0003_access_scope"),
        ("users", "0002_plan_features"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("STUDENT", "Студент"),
                    ("TEACHER", "Преподаватель"),
                    ("LAB_HEAD", "Заведующий лабораторией"),
                    ("LAB_ADMIN", "Сотрудник лаборатории"),
                    ("SYS_ADMIN", "Системный администратор"),
                ],
                default="STUDENT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="student_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="students",
                to="academics.studentgroup",
                verbose_name="Учебная группа",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="disciplines",
            field=models.ManyToManyField(
                blank=True,
                related_name="staff_profiles",
                to="academics.discipline",
                verbose_name="Дисциплины сотрудника",
            ),
        ),
    ]
