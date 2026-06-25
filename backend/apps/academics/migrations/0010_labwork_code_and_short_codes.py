import re

from django.db import migrations, models


def _normalize_short_code(raw: str) -> str:
    code = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "", (raw or "").upper())
    return code[:16]


def _initials_from_title(title: str, *, limit: int = 2) -> str:
    words = re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", title or "")
    if not words:
        return ""
    if len(words) == 1:
        return words[0][:limit].upper()
    return "".join(word[0].upper() for word in words[:limit])


def _build_candidate(number: int, discipline) -> str:
    faculty_code = "НГФ"
    department_code = "БК"
    discipline_code = "ДИС"
    if discipline is not None:
        department = getattr(discipline, "department", None)
        if department is not None:
            department_code = _normalize_short_code(getattr(department, "short_code", "")) or _initials_from_title(
                department.title
            )
        discipline_code = _normalize_short_code(getattr(discipline, "short_code", "")) or _initials_from_title(
            discipline.title
        )
    department_code = department_code or "БК"
    discipline_code = discipline_code or "ДИС"
    return f"{faculty_code}-{department_code}-{discipline_code}-{number}"


def backfill_short_codes_and_labwork_codes(apps, schema_editor):
    Department = apps.get_model("academics", "Department")
    Discipline = apps.get_model("academics", "Discipline")
    LabWork = apps.get_model("academics", "LabWork")

    for department in Department.objects.filter(short_code="").iterator():
        generated = _initials_from_title(department.title) or f"D{department.pk}"
        department.short_code = generated[:16]
        department.save(update_fields=["short_code"])

    for discipline in Discipline.objects.filter(short_code="").iterator():
        generated = _initials_from_title(discipline.title) or f"S{discipline.pk}"
        discipline.short_code = generated[:16]
        discipline.save(update_fields=["short_code"])

    used_codes = set(
        LabWork.objects.exclude(code__isnull=True).exclude(code="").values_list("code", flat=True)
    )
    for lab_work in LabWork.objects.order_by("pk").iterator():
        if lab_work.code:
            continue
        discipline = lab_work.disciplines.select_related("department").order_by("pk").first()
        base = _build_candidate(lab_work.number, discipline)
        candidate = base
        suffix = 2
        while candidate in used_codes:
            candidate = f"{base}-{suffix}"
            suffix += 1
        lab_work.code = candidate
        lab_work.save(update_fields=["code"])
        used_codes.add(candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0009_labwork_disciplines_m2m"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="short_code",
            field=models.CharField(blank=True, max_length=16, verbose_name="Короткий код"),
        ),
        migrations.AddField(
            model_name="discipline",
            name="short_code",
            field=models.CharField(blank=True, max_length=16, verbose_name="Короткий код"),
        ),
        migrations.AddField(
            model_name="labwork",
            name="code",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="Код ЛР"),
        ),
        migrations.RunPython(backfill_short_codes_and_labwork_codes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="labwork",
            constraint=models.UniqueConstraint(
                condition=models.Q(code__isnull=False),
                fields=("code",),
                name="academics_labwork_code_unique_not_null",
            ),
        ),
    ]
