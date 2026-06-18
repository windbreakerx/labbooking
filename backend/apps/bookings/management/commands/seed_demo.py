from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.academics.models import Discipline, LabWork, Semester
from apps.scheduling.models import Holiday, LabSession, LabSessionStatus, LabStand, Room, TrainingCenter
from apps.users.models import User, UserRole


class Command(BaseCommand):
    help = "Загрузка пилотных данных комплексной лаборатории нефтегазового факультета"

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            type=int,
            default=2,
            help="На сколько недель вперёд создать слоты (по умолчанию: 2)",
        )

    def _upsert_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: str,
        is_staff: bool = False,
        group_name: str = "",
        student_id: str = "",
        training_center=None,
    ):
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "is_staff": is_staff,
            },
        )
        user.set_password(password)
        user.save(update_fields=["password"])

        profile = user.profile
        profile.group_name = group_name
        profile.student_id = student_id
        profile.training_center = training_center
        profile.save()
        return user

    @staticmethod
    def _build_weekday_datetime(base_date, week_shift: int, weekday: int, hour: int, minute: int):
        target_date = base_date + timedelta(days=week_shift * 7 + weekday)
        tz = timezone.get_current_timezone()
        return timezone.make_aware(
            datetime.combine(target_date, time(hour=hour, minute=minute)),
            tz,
        )

    @staticmethod
    def _code(prefix: str, index: int) -> str:
        return f"{prefix}-{index:03d}"

    def handle(self, *args, **options):
        weeks = max(1, options["weeks"])
        today = timezone.localdate()
        Semester.objects.update(is_active=False)
        semester, _ = Semester.objects.update_or_create(
            name="Пилот 2026/2027 (нефтегаз)",
            defaults={
                "start_date": today - timedelta(days=7),
                "end_date": today + timedelta(days=140),
                "is_active": True,
            },
        )

        training_center, _ = TrainingCenter.objects.update_or_create(
            number=1,
            defaults={"name": "Комплексная учебная лаборатория нефтегазового факультета"},
        )

        rooms_payload = [
            ("1123", 10),
            ("1124", 15),
            ("2105", 21),
            ("2111", 15),
            ("2112", 20),
            ("2113", 15),
            ("2114", 5),
            ("2115", 21),
            ("2116", 16),
            ("2117", 15),
            ("2118", 5),
            ("3314", 14),
            ("3316", 15),
            ("3420", 24),
            ("3428", 44),
        ]
        rooms = {}
        for room_number, capacity in rooms_payload:
            room, _ = Room.objects.update_or_create(
                training_center=training_center,
                number=room_number,
                defaults={"capacity": capacity},
            )
            rooms[room_number] = room

        staff_payload = [
            ("zavlab.pilot@spmi.ru", "Павел", "Логинов"),
            ("operator1.pilot@spmi.ru", "Ольга", "Егорова"),
            ("operator2.pilot@spmi.ru", "Дмитрий", "Белов"),
        ]
        for email, first_name, last_name in staff_payload:
            self._upsert_user(
                email=email,
                password="pilot123",
                first_name=first_name,
                last_name=last_name,
                role=UserRole.LAB_ADMIN,
                is_staff=True,
                training_center=training_center,
            )

        teachers = []
        teachers_payload = [
            ("teacher.tng@spmi.ru", "Ирина", "Соколова"),
            ("teacher.bur@spmi.ru", "Андрей", "Мартынов"),
            ("teacher.razr@spmi.ru", "Сергей", "Климов"),
            ("teacher.gas@spmi.ru", "Виктория", "Лапина"),
        ]
        for email, first_name, last_name in teachers_payload:
            teachers.append(
                self._upsert_user(
                    email=email,
                    password="pilot123",
                    first_name=first_name,
                    last_name=last_name,
                    role=UserRole.TEACHER,
                    is_staff=False,
                    training_center=training_center,
                )
            )

        student_last_names = [
            "Иванов",
            "Петров",
            "Сидоров",
            "Кузнецов",
            "Смирнов",
            "Волков",
            "Соколов",
            "Орлов",
            "Егоров",
            "Лебедев",
        ]
        student_first_names = [
            "Алексей",
            "Денис",
            "Никита",
            "Павел",
            "Илья",
            "Мария",
            "Анна",
            "Екатерина",
            "София",
            "Полина",
        ]
        groups_payload = [
            ("ТНГ-24", 24),
            ("ГРП-24", 23),
            ("ЭХТ-24", 21),
            ("НГС-18-2", 22),
        ]
        student_counter = 1
        for group_name, group_size in groups_payload:
            for i in range(group_size):
                first_name = student_first_names[(student_counter + i) % len(student_first_names)]
                last_name = student_last_names[(student_counter + i) % len(student_last_names)]
                self._upsert_user(
                    email=f"student{student_counter:03d}@stud.local",
                    password="student123",
                    first_name=first_name,
                    last_name=last_name,
                    role=UserRole.STUDENT,
                    is_staff=False,
                    group_name=group_name,
                    student_id=f"ST-{today.year}-{student_counter:04d}",
                )
                student_counter += 1

        departments = {
            "Кафедра транспорта и хранения нефти и газа": [
                "Основы безопасной эксплуатации нефтегазового оборудования",
                "Эксплуатация насосных и компрессорных станций",
                "Диагностика объектов систем газораспределения и газопотребления",
                "Физические основы неразрушающего контроля материалов",
                "Диагностика объектов транспорта и хранения нефти и газа",
                "Защита газопроводов от коррозии",
                "Техническая диагностика газонефтепроводов",
                "Монтаж и ремонт газового оборудования",
                "Эксплуатация сетей газораспределения и газопотребления",
                "Ремонт и обслуживание газонефтепроводов",
                "Обслуживание и ремонт линейной части газонефтепроводов",
            ],
            "Кафедра бурения скважин": [
                "Техника и технология бурения нефтяных и газовых скважин",
                "Буровые и тампонажные растворы",
                "Осложнения и аварии в бурении",
                "Осложнения и аварии при бурении на шельфе",
                "Предупреждение и ликвидация аварий в скважинах",
                "Разобщение пластов и освоение скважин",
                "Реконструкция и восстановление скважин",
                "Заканчивание скважин",
                "Подводное оборудование и управление скважиной",
                "Буровые промывочные и тампонажные растворы",
                "Бурение скважин на шельфе",
                "Физико-химия буровых технологических жидкостей",
                "Проектирование и эксплуатация геологоразведочного оборудования",
            ],
            "Кафедра разработки и эксплуатации нефтяных и газовых месторождений": [
                "Разработка нефтяных и газовых месторождений",
                "Текущий и капитальный ремонт скважин",
                "Гидродинамические методы исследования скважин и пластов",
                "Сбор и подготовка скважинной продукции",
                "Внутрипромысловый сбор и подготовка скважинной продукции на шельфе",
                "Основы разработки нефтяных и газовых месторождений",
                "Основы реологии нефти",
            ],
        }

        special_lab_specs = {
            "Ремонт и обслуживание газонефтепроводов": [
                {
                    "title": "Врезка в газопровод под давлением",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Устройство для врезки под давлением в трубопровод Tonisco B30 Ду 40-200 мм",
                    "slot": (0, 10, 35),  # Monday, 2nd pair
                    "target_groups": "ТНГ, ГРП, ЭХТ",
                },
                {
                    "title": "Сварка ПЭ трубопровода нагретым инструментом в стык",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Аппарат для стыковой сварки полиэтиленовых труб и фитингов Nowatech ZHCN-160CNC",
                    "slot": (0, 10, 35),  # parallel to previous lab
                    "target_groups": "ТНГ, ГРП, ЭХТ",
                },
            ],
            "Эксплуатация сетей газораспределения и газопотребления": [
                {
                    "title": "Подготовка ГРУ к запуску. Запуск ГРУ",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Газорегуляторная установка ГРУ-036М-07-2ПУ1",
                    "slot": (1, 10, 35),
                    "target_groups": "ТНГ, ГРП",
                },
                {
                    "title": "Настройка ПЗК и ПСК",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Газорегуляторная установка ГРУ-036М-07-2ПУ1",
                    "slot": (1, 12, 35),
                    "target_groups": "ТНГ, ГРП",
                },
                {
                    "title": "Перевод ГРУ на резервную линию редуцирования",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Газорегуляторная установка ГРУ-036М-07-2ПУ1",
                    "slot": (2, 10, 35),
                    "target_groups": "ТНГ, ГРП",
                },
                {
                    "title": "Запуск ГРУ с двумя ступенями редуцирования",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Газорегуляторная установка ГРУ-036М-07-2ПУ1",
                    "slot": (2, 12, 35),
                    "target_groups": "ТНГ, ГРП",
                },
                {
                    "title": "Подготовка ШРП к запуску. Запуск ШРП",
                    "duration": 90,
                    "capacity": 3,
                    "room_number": "1123",
                    "stand_name": "Газорегуляторная установка ГРУ-036М-07-2ПУ1",
                    "slot": (3, 10, 35),
                    "target_groups": "ТНГ, ГРП",
                },
            ],
            "Техника и технология бурения нефтяных и газовых скважин": [
                {
                    "title": "Определение категории горных пород по буримости на основе объединенного показателя динамической прочности и абразивности",
                    "duration": 90,
                    "capacity": 10,
                    "room_number": "2105",
                    "stand_name": "Прибор ПОАП-2м",
                    "slot": (0, 14, 15),
                    "target_groups": "НГС-**-*",
                }
            ],
        }

        discipline_counter = 1
        generic_slots = [
            (0, 8, 50),
            (0, 10, 35),
            (1, 12, 35),
            (2, 14, 15),
            (3, 15, 55),
            (4, 17, 30),
        ]
        generic_room_numbers = list(rooms.keys())
        lab_session_plan = []
        for department_name, discipline_titles in departments.items():
            for discipline_title in discipline_titles:
                code = self._code("NGF", discipline_counter)
                discipline_counter += 1
                discipline, _ = Discipline.objects.update_or_create(
                    title=discipline_title,
                    defaults={
                        "code": code,
                        "description": f"{department_name}. Пилотный набор 2026/2027.",
                        "semester": semester,
                        "is_published": True,
                    },
                )

                lab_specs = special_lab_specs.get(discipline_title)
                if lab_specs is None:
                    slot_weekday, slot_hour, slot_minute = generic_slots[(discipline_counter - 1) % len(generic_slots)]
                    room_number = generic_room_numbers[(discipline_counter - 1) % len(generic_room_numbers)]
                    lab_specs = [
                        {
                            "title": f"Лабораторная работа по дисциплине «{discipline_title}»",
                            "duration": 90,
                            "capacity": min(12, rooms[room_number].capacity),
                            "room_number": room_number,
                            "stand_name": "",
                            "slot": (slot_weekday, slot_hour, slot_minute),
                            "target_groups": "Все пилотные группы",
                        }
                    ]

                for number, spec in enumerate(lab_specs, start=1):
                    lab_work, _ = LabWork.objects.update_or_create(
                        discipline=discipline,
                        number=number,
                        defaults={
                            "title": spec["title"],
                            "description": f"Целевые группы: {spec['target_groups']}",
                            "duration_minutes": spec["duration"],
                            "is_published": True,
                        },
                    )
                    if spec["stand_name"]:
                        LabStand.objects.update_or_create(
                            name=spec["stand_name"],
                            training_center=training_center,
                            room=rooms[spec["room_number"]],
                            defaults={
                                "inventory_number": f"INV-{lab_work.id:05d}",
                                "description": f"Стенд для дисциплины «{discipline_title}».",
                            },
                        )
                    lab_session_plan.append(
                        {
                            "lab_work": lab_work,
                            "room": rooms[spec["room_number"]],
                            "capacity": spec["capacity"],
                            "slot": spec["slot"],
                        }
                    )

        # Слоты с понедельника текущей недели, иначе в чт–вс не остаётся дат для записи.
        current_monday = today - timedelta(days=today.weekday())
        now = timezone.now()
        created_sessions = 0
        for week_shift in range(weeks):
            for index, plan in enumerate(lab_session_plan):
                teacher = teachers[index % len(teachers)]
                weekday, hour, minute = plan["slot"]
                starts_at = self._build_weekday_datetime(
                    base_date=current_monday,
                    week_shift=week_shift,
                    weekday=weekday,
                    hour=hour,
                    minute=minute,
                )
                if starts_at <= now:
                    continue
                created_sessions += 1
                LabSession.objects.update_or_create(
                    lab_work=plan["lab_work"],
                    room=plan["room"],
                    semester=semester,
                    starts_at=starts_at,
                    defaults={
                        "ends_at": starts_at + timedelta(minutes=plan["lab_work"].duration_minutes),
                        "capacity": min(plan["capacity"], plan["room"].capacity),
                        "status": LabSessionStatus.OPEN,
                        "teacher": teacher,
                    },
                )

        Holiday.objects.get_or_create(date=date(2026, 11, 4), defaults={"name": "День народного единства"})

        self.stdout.write(self.style.SUCCESS("Пилотные данные нефтегазовой лаборатории загружены."))
        self.stdout.write(f"Создано/обновлено будущих слотов: {created_sessions}")
        self.stdout.write("Сотрудники: zavlab.pilot@spmi.ru, operator1.pilot@spmi.ru, operator2.pilot@spmi.ru / pilot123")
        self.stdout.write("Преподаватели: teacher.tng@spmi.ru, teacher.bur@spmi.ru, teacher.razr@spmi.ru, teacher.gas@spmi.ru / pilot123")
        self.stdout.write("Студенты: student001..student090@stud.local / student123")
