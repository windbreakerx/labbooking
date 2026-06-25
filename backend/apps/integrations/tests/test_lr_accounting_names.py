from dataclasses import dataclass

from apps.integrations.lr_accounting.names import (
    DisplayName,
    feminize_last_name,
    infer_gender,
    masculinize_last_name,
    shuffle_student_display_names,
)


@dataclass
class _Student:
    number: int
    last_name: str
    first_name: str


def _student(last_name: str, first_name: str, number: int = 1) -> _Student:
    return _Student(number=number, last_name=last_name, first_name=first_name)


def test_infer_gender_from_patronymic():
    assert infer_gender(first="Иван", patronymic="Иванович", last_name="Петров") == "male"
    assert infer_gender(first="Мария", patronymic="Ивановна", last_name="Петрова") == "female"


def test_feminize_and_masculinize_last_name():
    assert feminize_last_name("Петров") == "Петрова"
    assert feminize_last_name("Горский") == "Горская"
    assert masculinize_last_name("Петрова") == "Петров"
    assert masculinize_last_name("Горская") == "Горский"


def test_shuffle_keeps_gender_consistency():
    students = [
        _student("Иванов", "Иван Иванович", 1),
        _student("Петров", "Пётр Петрович", 2),
        _student("Сидорова", "Мария Ивановна", 3),
        _student("Козлова", "Анна Петровна", 4),
    ]
    shuffled = shuffle_student_display_names(students, seed=42)

    for original, display in zip(students, shuffled, strict=True):
        _, first, patronymic = display.first_name.partition(" ")
        gender = infer_gender(first=first, patronymic=patronymic, last_name=display.last_name)
        source_gender = infer_gender(
            first=original.first_name.split()[0],
            patronymic=original.first_name.split()[1] if " " in original.first_name else "",
            last_name=original.last_name,
        )
        assert gender == source_gender


def test_shuffle_changes_names_between_students():
    students = [
        _student("Иванов", "Иван Иванович", 1),
        _student("Петров", "Пётр Петрович", 2),
        _student("Сидоров", "Сергей Сергеевич", 3),
    ]
    shuffled = shuffle_student_display_names(students, seed=7)
    original_pairs = {(s.last_name, s.first_name) for s in students}
    shuffled_pairs = {(d.last_name, d.first_name) for d in shuffled}
    assert shuffled_pairs != original_pairs


def test_shuffle_is_reproducible_with_seed():
    students = [
        _student("Иванов", "Иван Иванович", 1),
        _student("Петрова", "Мария Ивановна", 2),
    ]
    first = shuffle_student_display_names(students, seed=123)
    second = shuffle_student_display_names(students, seed=123)
    assert first == second


def test_shuffle_preserves_count():
    students = [_student("Иванов", "Иван Иванович", index) for index in range(1, 6)]
    shuffled = shuffle_student_display_names(students, seed=1)
    assert len(shuffled) == len(students)
    assert all(isinstance(item, DisplayName) for item in shuffled)
