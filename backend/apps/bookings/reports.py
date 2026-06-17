from io import BytesIO

from apps.bookings.models import Booking, BookingStatus


def generate_report(
    report_type: str,
    date_from: str | None = None,
    date_to: str | None = None,
    discipline_id: str | None = None,
) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active

    qs = Booking.objects.select_related(
        "student",
        "lab_work",
        "discipline",
        "room",
        "room__training_center",
    )
    if date_from:
        qs = qs.filter(scheduled_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(scheduled_at__date__lte=date_to)
    if discipline_id:
        qs = qs.filter(discipline_id=discipline_id)

    if report_type == "bookings":
        ws.title = "Записи"
        ws.append(["Студент", "Email", "Дисциплина", "ЛР", "Дата", "УЦ", "Ауд.", "Статус"])
        for b in qs.order_by("scheduled_at"):
            ws.append([
                b.student.full_name,
                b.student.email,
                b.discipline.title,
                b.lab_work.title,
                b.scheduled_at.strftime("%d.%m.%Y %H:%M"),
                b.room.training_center.number,
                b.room.number,
                b.get_current_status_display(),
            ])
    elif report_type == "attendance":
        ws.title = "Посещаемость"
        qs = qs.filter(current_status__in=[BookingStatus.VISITED, BookingStatus.NO_SHOW])
        ws.append(["Студент", "Дисциплина", "ЛР", "Дата", "Статус"])
        for b in qs.order_by("scheduled_at"):
            ws.append([
                b.student.full_name,
                b.discipline.title,
                b.lab_work.title,
                b.scheduled_at.strftime("%d.%m.%Y %H:%M"),
                b.get_current_status_display(),
            ])
    elif report_type == "discipline_summary":
        ws.title = "Свод по дисциплине"
        ws.append(["Дисциплина", "Записано", "Посетили", "Неявки", "Отмены"])
        disciplines = {}
        for b in qs:
            key = b.discipline.title
            if key not in disciplines:
                disciplines[key] = {"booked": 0, "visited": 0, "no_show": 0, "cancelled": 0}
            if b.current_status == BookingStatus.BOOKED:
                disciplines[key]["booked"] += 1
            elif b.current_status == BookingStatus.VISITED:
                disciplines[key]["visited"] += 1
            elif b.current_status == BookingStatus.NO_SHOW:
                disciplines[key]["no_show"] += 1
            elif b.current_status == BookingStatus.CANCELLED:
                disciplines[key]["cancelled"] += 1
        for title, counts in sorted(disciplines.items()):
            ws.append([
                title,
                counts["booked"],
                counts["visited"],
                counts["no_show"],
                counts["cancelled"],
            ])
    else:
        ws.append(["Неизвестный тип отчёта"])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
