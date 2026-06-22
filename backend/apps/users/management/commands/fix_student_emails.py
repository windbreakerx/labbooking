from django.core.management.base import BaseCommand

from apps.integrations.lr_accounting.students import allocate_student_id, new_year_counters, student_email
from apps.users.models import User, UserRole


class Command(BaseCommand):
    help = "Перевести студентов на почту s<номер_зачётки>@stud.spmi.ru"

    def handle(self, *args, **options):
        counters = new_year_counters()
        updated = 0
        users = (
            User.objects.filter(role=UserRole.STUDENT)
            .select_related("profile")
            .order_by("profile__group_name", "id")
        )
        for user in users:
            group_name = user.profile.group_name
            if not group_name:
                self.stderr.write(f"Пропуск {user.pk}: нет группы")
                continue
            record_id = allocate_student_id(group_name, counters)
            new_email = student_email(record_id)
            user.email = new_email
            user.save(update_fields=["email"])
            user.profile.student_id = record_id
            user.profile.save(update_fields=["student_id"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Обновлено студентов: {updated}"))
