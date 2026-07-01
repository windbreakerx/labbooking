import pytest

from apps.academics.models import Discipline, LabWork, Semester, StudentGroup
from apps.academics.services.lab_work_dedupe import dedupe_lab_works
from apps.scheduling.models import Room, TrainingCenter


@pytest.mark.django_db
def test_dedupe_lab_works_merges_same_title_and_room():
    semester = Semester.objects.create(name="Test", is_active=True)
    discipline = Discipline.objects.create(title="Тестовая дисциплина", semester=semester, code="TST-001")
    training_center = TrainingCenter.objects.create(number=99, name="Test TC")
    room = Room.objects.create(training_center=training_center, number="9999", capacity=10)

    first = LabWork.objects.create(number=1, title="Лаб. раб. №1. Определение плотности", default_room=room)
    second = LabWork.objects.create(number=2, title="Лаб. раб. №1. Определение плотности.", default_room=room)
    first.disciplines.add(discipline)
    second.disciplines.add(discipline)

    stats = dedupe_lab_works()
    assert stats["merged_rows"] == 1
    assert LabWork.objects.count() == 1
    keeper = LabWork.objects.get()
    assert keeper.disciplines.filter(pk=discipline.pk).exists()


@pytest.mark.django_db
def test_dedupe_keeps_different_rooms():
    semester = Semester.objects.create(name="Test", is_active=True)
    discipline = Discipline.objects.create(title="Дисциплина", semester=semester, code="TST-002")
    training_center = TrainingCenter.objects.create(number=98, name="Test TC 2")
    room_a = Room.objects.create(training_center=training_center, number="1001", capacity=10)
    room_b = Room.objects.create(training_center=training_center, number="1002", capacity=10)

    lab_a = LabWork.objects.create(number=1, title="Одна и та же ЛР", default_room=room_a)
    lab_b = LabWork.objects.create(number=2, title="Одна и та же ЛР", default_room=room_b)
    lab_a.disciplines.add(discipline)
    lab_b.disciplines.add(discipline)

    stats = dedupe_lab_works()
    assert stats["merged_rows"] == 0
    assert LabWork.objects.count() == 2
