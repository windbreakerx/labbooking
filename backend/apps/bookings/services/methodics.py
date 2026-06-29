from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile

from apps.academics.models import LabWork, LabWorkMethodics
from apps.academics.querysets import staff_managed_lab_works_qs
from apps.bookings.services.lab_head import lab_head_lab_work_in_scope
from apps.users.models import User

METHODICS_MAX_FILE_SIZE = 10 * 1024 * 1024


def _lab_work_in_user_scope(user: User, lab_work: LabWork) -> bool:
    if lab_head_lab_work_in_scope(user, lab_work.pk):
        return True
    return staff_managed_lab_works_qs(user).filter(pk=lab_work.pk).exists()


def upload_lab_work_methodics(
    user: User,
    lab_work: LabWork,
    files: list[UploadedFile],
) -> tuple[int, list[str]]:
    if not _lab_work_in_user_scope(user, lab_work):
        raise ValueError("Лабораторная работа недоступна.")

    uploaded = 0
    errors: list[str] = []
    for file in files:
        if file.size > METHODICS_MAX_FILE_SIZE:
            errors.append(f"«{file.name}» превышает 10 МБ.")
            continue
        if not file.name.lower().endswith(".pdf"):
            errors.append(f"«{file.name}» должен быть PDF.")
            continue
        LabWorkMethodics.objects.create(lab_work=lab_work, file=file)
        uploaded += 1
    return uploaded, errors


def delete_lab_work_methodics(user: User, lab_work: LabWork, methodics_id: int) -> str:
    if not _lab_work_in_user_scope(user, lab_work):
        raise ValueError("Лабораторная работа недоступна.")
    methodics = LabWorkMethodics.objects.filter(pk=methodics_id, lab_work=lab_work).first()
    if not methodics:
        raise ValueError("Методичка не найдена.")
    display_name = methodics.display_name
    methodics.file.delete(save=False)
    methodics.delete()
    return display_name
