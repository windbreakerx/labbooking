"""Merge duplicate LabWork rows that share title and default room."""

from __future__ import annotations

from collections import defaultdict

from django.db import transaction

from apps.academics.models import LabWork
from apps.academics.services.catalog_normalize import lab_work_match_key
from apps.bookings.models import Booking
from apps.scheduling.models import LabSession, ScheduleEntry


def _merge_m2m(keeper: LabWork, duplicate: LabWork, field_name: str) -> None:
    manager = getattr(keeper, field_name)
    manager.add(*getattr(duplicate, field_name).all())


def merge_lab_work_pair(keeper: LabWork, duplicate: LabWork) -> None:
    if keeper.pk == duplicate.pk:
        return

    _merge_m2m(keeper, duplicate, "disciplines")
    _merge_m2m(keeper, duplicate, "training_centers")
    _merge_m2m(keeper, duplicate, "laboratories")

    for group in duplicate.student_groups.all():
        group.lab_works.add(keeper)

    if not keeper.code and duplicate.code:
        keeper.code = duplicate.code
    if not keeper.description and duplicate.description:
        keeper.description = duplicate.description
    if not keeper.primary_stand_id and duplicate.primary_stand_id:
        keeper.primary_stand_id = duplicate.primary_stand_id
    if duplicate.duration_minutes and keeper.duration_minutes == 90 and duplicate.duration_minutes != 90:
        keeper.duration_minutes = duplicate.duration_minutes
    if duplicate.capacity and keeper.capacity == 30 and duplicate.capacity != 30:
        keeper.capacity = duplicate.capacity
    keeper.save()

    LabSession.objects.filter(lab_work=duplicate).update(lab_work=keeper)
    Booking.objects.filter(lab_work=duplicate).update(lab_work=keeper)
    ScheduleEntry.objects.filter(lab_work=duplicate).update(lab_work=keeper)

    duplicate.methodics_files.update(lab_work=keeper)
    duplicate.delete()


@transaction.atomic
def dedupe_lab_works(*, dry_run: bool = False) -> dict[str, int]:
    buckets: dict[tuple[str, int | None], list[LabWork]] = defaultdict(list)
    for lab_work in LabWork.objects.select_related("default_room").order_by("pk"):
        room_id = lab_work.default_room_id
        buckets[lab_work_match_key(lab_work.title, room_id)].append(lab_work)

    merged = 0
    groups = 0
    for items in buckets.values():
        if len(items) < 2:
            continue
        groups += 1
        keeper = items[0]
        for duplicate in items[1:]:
            if dry_run:
                merged += 1
                continue
            merge_lab_work_pair(keeper, duplicate)
            merged += 1

    return {"duplicate_groups": groups, "merged_rows": merged}
