import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("academics", "0001_initial"),
        ("scheduling", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=256)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("OPEN", "Открыт"), ("ANSWERED", "Отвечен"), ("CLOSED", "Закрыт")], default="OPEN", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="support_tickets", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Обращение",
                "verbose_name_plural": "Обращения",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SupportMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="bookings.supportticket")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scheduled_at", models.DateTimeField(verbose_name="Дата и время ЛР")),
                ("current_status", models.CharField(choices=[("BOOKED", "Записан"), ("NO_SHOW", "Неявка"), ("CANCELLED", "Отменил запись"), ("REACCESS", "Повторный доступ"), ("VISITED", "Посетил")], default="BOOKED", max_length=16)),
                ("registration_type", models.CharField(choices=[("AUTO", "Автоматическая"), ("MANUAL", "Не автоматическая")], default="AUTO", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("discipline", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="academics.discipline")),
                ("lab_session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="scheduling.labsession")),
                ("lab_work", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="academics.labwork")),
                ("registered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registered_bookings", to=settings.AUTH_USER_MODEL)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="scheduling.room")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Запись",
                "verbose_name_plural": "Записи",
                "ordering": ["-scheduled_at"],
            },
        ),
        migrations.CreateModel(
            name="BookingStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("BOOKED", "Записан"), ("NO_SHOW", "Неявка"), ("CANCELLED", "Отменил запись"), ("REACCESS", "Повторный доступ"), ("VISITED", "Посетил")], max_length=16)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("note", models.TextField(blank=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="bookings.booking")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "История статуса",
                "verbose_name_plural": "История статусов",
                "ordering": ["changed_at"],
            },
        ),
        migrations.CreateModel(
            name="WaitlistEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("lab_session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="waitlist", to="scheduling.labsession")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="waitlist_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Очередь",
                "verbose_name_plural": "Очередь",
                "ordering": ["position"],
                "unique_together": {("lab_session", "student")},
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=64)),
                ("entity_type", models.CharField(max_length=64)),
                ("entity_id", models.PositiveIntegerField()),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Аудит",
                "verbose_name_plural": "Аудит",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["student", "discipline", "current_status"], name="bookings_bo_student_6e2f8a_idx"),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["scheduled_at", "current_status"], name="bookings_bo_schedul_0a3b2c_idx"),
        ),
    ]
