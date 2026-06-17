"""Integration stub for ISAUП Деканат sync (post-MVP)."""

import csv
from pathlib import Path

from django.contrib.auth import get_user_model

from apps.academics.models import Discipline, Semester

User = get_user_model()


class DekanatClient:
    """Клиент синхронизации с Деканатом. API — post-MVP; CSV — для пилота."""

    def __init__(self, api_url: str = "", api_key: str = ""):
        self.api_url = api_url
        self.api_key = api_key

    def sync_students(self):
        if self.api_url:
            raise NotImplementedError("Dekanat API sync not configured")
        raise NotImplementedError("Use management command: import_dekanat_csv students")

    def sync_teachers(self):
        if self.api_url:
            raise NotImplementedError("Dekanat API sync not configured")
        raise NotImplementedError("Use management command: import_dekanat_csv teachers")

    def sync_disciplines(self):
        if self.api_url:
            raise NotImplementedError("Dekanat API sync not configured")
        raise NotImplementedError("Use management command: import_dekanat_csv disciplines")

    def sync_departments(self):
        raise NotImplementedError("Dekanat integration not configured")

    def import_students_csv(self, path: str | Path) -> int:
        from apps.users.models import UserProfile, UserRole

        count = 0
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                email = row.get("email", "").strip()
                if not email or User.objects.filter(email=email).exists():
                    continue
                user = User.objects.create_user(
                    email=email,
                    password=row.get("password", "changeme"),
                    first_name=row.get("first_name", ""),
                    last_name=row.get("last_name", ""),
                    role=UserRole.STUDENT,
                )
                UserProfile.objects.filter(user=user).update(
                    group_name=row.get("group", ""),
                    dekanat_id=row.get("dekanat_id", ""),
                )
                count += 1
        return count

    def import_disciplines_csv(self, path: str | Path) -> int:
        semester = Semester.objects.filter(is_active=True).first()
        count = 0
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                title = row.get("title", "").strip()
                if not title:
                    continue
                Discipline.objects.get_or_create(
                    title=title,
                    defaults={
                        "code": row.get("code", ""),
                        "semester": semester,
                        "dekanat_id": row.get("dekanat_id", ""),
                    },
                )
                count += 1
        return count
