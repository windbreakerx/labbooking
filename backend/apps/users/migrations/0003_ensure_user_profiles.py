from django.db import migrations


def ensure_user_profiles(apps, schema_editor):
    User = apps.get_model("users", "User")
    UserProfile = apps.get_model("users", "UserProfile")
    for user in User.objects.all().iterator():
        UserProfile.objects.get_or_create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_plan_features"),
    ]

    operations = [
        migrations.RunPython(ensure_user_profiles, migrations.RunPython.noop),
    ]
