from django.db import migrations, models


DEPARTMENTS = [
    (
        0,
        "Кафедра транспорта и хранения нефти и газа",
        [
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
    ),
    (
        1,
        "Кафедра бурения скважин",
        [
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
    ),
    (
        2,
        "Кафедра разработки и эксплуатации нефтяных и газовых месторождений",
        [
            "Разработка нефтяных и газовых месторождений",
            "Текущий и капитальный ремонт скважин",
            "Гидродинамические методы исследования скважин и пластов",
            "Сбор и подготовка скважинной продукции",
            "Внутрипромысловый сбор и подготовка скважинной продукции на шельфе",
            "Основы разработки нефтяных и газовых месторождений",
            "Основы реологии нефти",
        ],
    ),
]


def populate_departments(apps, schema_editor):
    Department = apps.get_model("academics", "Department")
    Discipline = apps.get_model("academics", "Discipline")
    for ordering, title, discipline_titles in DEPARTMENTS:
        department, _ = Department.objects.get_or_create(
            title=title,
            defaults={"ordering": ordering},
        )
        if department.ordering != ordering:
            department.ordering = ordering
            department.save(update_fields=["ordering"])
        Discipline.objects.filter(title__in=discipline_titles).update(department_id=department.id)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0007_lab_work_stand_and_duration_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=256, unique=True, verbose_name="Название")),
                ("ordering", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Кафедра",
                "verbose_name_plural": "Кафедры",
                "ordering": ["ordering", "title"],
            },
        ),
        migrations.AddField(
            model_name="discipline",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="disciplines",
                to="academics.department",
                verbose_name="Кафедра",
            ),
        ),
        migrations.RunPython(populate_departments, migrations.RunPython.noop),
    ]
