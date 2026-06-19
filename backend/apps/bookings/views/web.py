import calendar
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.academics.models import Discipline, LabWork
from apps.academics.querysets import (
    published_disciplines_qs,
    staff_disciplines_qs,
    staff_lab_works_qs,
    staff_managed_disciplines_qs,
    staff_managed_lab_works_qs,
    student_disciplines_qs,
    student_lab_works_qs,
    student_support_training_centers_qs,
)
from apps.bookings.models import Booking, BookingStatus, SupportTicket
from apps.bookings.services import (
    BookingError,
    BookingService,
    filter_staff_bookings,
    is_staff_user,
    search_students_for_staff,
    staff_can_access_scoped_object,
    staff_lab_filter,
)
from apps.bookings.services.session_availability import (
    get_session_filter_options,
    get_sessions_for_date_time,
    get_sessions_for_selection,
    pair_meta_by_time,
    staff_manual_sessions_qs,
)
from apps.scheduling.models import LabSession, TrainingCenter
from apps.users.models import User, UserRole

WEEKDAY_HEADERS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def build_calendar_months(date_options: list[dict]) -> list[dict]:
    option_by_date = {}
    parsed_dates = []
    for option in date_options:
        value = option.get("value")
        if not value:
            continue
        parsed = datetime.fromisoformat(value).date()
        option_by_date[parsed] = option
        parsed_dates.append(parsed)

    if not parsed_dates:
        return []

    max_seats = max((option.get("available_seats", 0) for option in date_options), default=0)
    month_keys = sorted({(d.year, d.month) for d in parsed_dates})
    months = []
    for year, month in month_keys:
        month_calendar = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        weeks = []
        for week in month_calendar:
            cells = []
            for day in week:
                option = option_by_date.get(day)
                seats = option.get("available_seats", 0) if option else 0
                heat = round(seats / max_seats * 100) if max_seats and seats else 0
                cells.append(
                    {
                        "day": day.day,
                        "is_current_month": day.month == month,
                        "is_available": bool(option),
                        "value": option.get("value") if option else "",
                        "label": option.get("label") if option else "",
                        "available_seats": seats,
                        "heat": heat,
                    }
                )
            weeks.append(cells)
        months.append(
            {
                "title": f"{MONTH_NAMES[month]} {year}",
                "weeks": weeks,
                "weekday_headers": WEEKDAY_HEADERS,
            }
        )
    return months


MANUAL_BOOKING_PARTIAL_CONTEXT = {
    "filter_route": "staff-manual-filter",
    "filter_chain_selector": "#manual-filter-chain",
    "session_slot_selector": "#manual-session-slot",
    "book_btn_id": "manual-book-btn",
    "manual_mode": True,
}


def _staff_manual_sessions_qs(user, lab_work_id: int):
    return staff_lab_filter(staff_manual_sessions_qs(lab_work_id), user)


def _render_manual_filter_partial(request, lab_work_id: int, date, time_str, tc_number, room_id):
    sessions_qs = _staff_manual_sessions_qs(request.user, lab_work_id)
    ctx = {**MANUAL_BOOKING_PARTIAL_CONTEXT, "lab_work_id": lab_work_id}

    if date and time_str and not room_id:
        sessions = list(
            get_sessions_for_date_time(
                lab_work_id,
                date,
                time_str,
                sessions_qs=sessions_qs,
            ).select_related("room", "room__training_center")
        )
        if len(sessions) == 1:
            pair_label = ""
            if meta := pair_meta_by_time(time_str):
                _, pair_label = meta
            return render(
                request,
                "bookings/partials/session_confirm.html",
                {
                    **ctx,
                    "session": sessions[0],
                    "date": date,
                    "time": time_str,
                    "pair_label": pair_label,
                },
            )
        if len(sessions) > 1:
            rooms = {s.room_id: s.room for s in sessions}
            return render(
                request,
                "bookings/partials/filter_room.html",
                {
                    **ctx,
                    "date": date,
                    "time": time_str,
                    "options": [
                        {
                            "value": str(room.pk),
                            "label": (
                                f"ауд. {room.number} "
                                f"(УЦ №{room.training_center.number})"
                            ),
                        }
                        for room in sorted(rooms.values(), key=lambda r: r.number)
                    ],
                },
            )

    if room_id and date and time_str:
        sessions = get_sessions_for_selection(
            lab_work_id,
            date,
            time_str,
            int(room_id),
            sessions_qs=sessions_qs,
        )
        return render(
            request,
            "bookings/partials/session_select.html",
            {**ctx, "sessions": sessions},
        )

    filter_data = get_session_filter_options(
        lab_work_id,
        date,
        time_str,
        tc_number,
        sessions_qs=sessions_qs,
    )
    template_map = {
        "date": "bookings/partials/filter_date_calendar.html",
        "time": "bookings/partials/filter_time.html",
        "training_center": "bookings/partials/filter_tc.html",
        "room": "bookings/partials/filter_room.html",
    }
    context = {
        **ctx,
        "options": filter_data["options"],
        "date": date,
        "time": time_str,
        "tc": tc_number,
    }
    if filter_data["level"] == "date":
        context["calendar_months"] = build_calendar_months(filter_data["options"])
    return render(request, template_map[filter_data["level"]], context)


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "bookings/home.html"


class DisciplineListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/disciplines.html"
    context_object_name = "disciplines"

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.STUDENT:
            return student_disciplines_qs(user)
        if is_staff_user(user):
            return staff_disciplines_qs(user)
        return published_disciplines_qs()


class LabWorkListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/lab_works.html"
    context_object_name = "lab_works"

    def get_queryset(self):
        user = self.request.user
        discipline_id = self.kwargs["discipline_id"]
        if user.role == UserRole.STUDENT:
            return student_lab_works_qs(user, discipline_id=discipline_id)
        if is_staff_user(user):
            return staff_lab_works_qs(user, discipline_id=discipline_id)
        from apps.academics.querysets import published_lab_works_qs

        return published_lab_works_qs(discipline_id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        discipline_id = self.kwargs["discipline_id"]
        if user.role == UserRole.STUDENT:
            discipline_qs = student_disciplines_qs(user)
        elif is_staff_user(user):
            discipline_qs = staff_disciplines_qs(user)
        else:
            discipline_qs = published_disciplines_qs()
        ctx["discipline"] = get_object_or_404(discipline_qs, pk=discipline_id)
        return ctx


class BookLabWorkWebView(LoginRequiredMixin, View):
    template_name = "bookings/book.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != UserRole.STUDENT:
            messages.error(request, "Запись доступна только студентам.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, lab_work_id):
        lab_work = get_object_or_404(
            student_lab_works_qs(request.user),
            pk=lab_work_id,
        )
        filter_data = get_session_filter_options(lab_work_id)
        return render(
            request,
            self.template_name,
            {
                "lab_work": lab_work,
                "filter_level": filter_data["level"],
                "filter_options": filter_data["options"],
                "calendar_months": build_calendar_months(filter_data["options"]),
            },
        )

    def post(self, request, lab_work_id):
        session_id = request.POST.get("session_id")
        service = BookingService(actor=request.user)
        try:
            service.create_booking(request.user, int(session_id))
            messages.success(request, "Вы успешно записались на лабораторную работу.")
        except (BookingError, ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect("my-bookings")


class BookFilterPartialView(LoginRequiredMixin, View):
    """HTMX partial для каскадных фильтров."""

    def get(self, request, lab_work_id):
        if request.user.role != UserRole.STUDENT:
            return HttpResponseForbidden()
        get_object_or_404(student_lab_works_qs(request.user), pk=lab_work_id)
        date = request.GET.get("date") or None
        time_str = request.GET.get("time") or None
        tc_number = request.GET.get("tc") or None
        room_id = request.GET.get("room") or None

        if date and time_str and not room_id:
            sessions = list(
                get_sessions_for_date_time(lab_work_id, date, time_str).select_related(
                    "room",
                    "room__training_center",
                )
            )
            if len(sessions) == 1:
                pair_label = ""
                if meta := pair_meta_by_time(time_str):
                    _, pair_label = meta
                return render(
                    request,
                    "bookings/partials/session_confirm.html",
                    {
                        "session": sessions[0],
                        "date": date,
                        "time": time_str,
                        "pair_label": pair_label,
                    },
                )
            if len(sessions) > 1:
                rooms = {s.room_id: s.room for s in sessions}
                return render(
                    request,
                    "bookings/partials/filter_room.html",
                    {
                        "lab_work_id": lab_work_id,
                        "date": date,
                        "time": time_str,
                        "options": [
                            {
                                "value": str(room.pk),
                                "label": (
                                    f"ауд. {room.number} "
                                    f"(УЦ №{room.training_center.number})"
                                ),
                            }
                            for room in sorted(rooms.values(), key=lambda r: r.number)
                        ],
                    },
                )

        if room_id and date and time_str:
            sessions = get_sessions_for_selection(lab_work_id, date, time_str, int(room_id))
            return render(
                request,
                "bookings/partials/session_select.html",
                {"sessions": sessions},
            )

        filter_data = get_session_filter_options(lab_work_id, date, time_str, tc_number)
        template_map = {
            "date": "bookings/partials/filter_date_calendar.html",
            "time": "bookings/partials/filter_time.html",
            "training_center": "bookings/partials/filter_tc.html",
            "room": "bookings/partials/filter_room.html",
        }
        context = {
            "lab_work_id": lab_work_id,
            "options": filter_data["options"],
            "date": date,
            "time": time_str,
            "tc": tc_number,
        }
        if filter_data["level"] == "date":
            context["calendar_months"] = build_calendar_months(filter_data["options"])
        return render(
            request,
            template_map[filter_data["level"]],
            context,
        )


class WaitlistJoinWebView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.role != UserRole.STUDENT:
            return redirect("home")
        session_id = request.POST.get("session_id")
        service = BookingService(actor=request.user)
        try:
            service.join_waitlist(request.user, int(session_id))
            messages.success(request, "Вы добавлены в очередь.")
        except (BookingError, ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect("my-bookings")


class MyBookingsWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/my_bookings.html"
    context_object_name = "bookings"

    def get_queryset(self):
        return Booking.objects.filter(student=self.request.user).select_related(
            "lab_work",
            "discipline",
            "room",
            "room__training_center",
        )


class BookingDetailWebView(LoginRequiredMixin, DetailView):
    template_name = "bookings/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        return Booking.objects.filter(student=self.request.user).select_related(
            "lab_work",
            "discipline",
            "room",
            "room__training_center",
        )


class CancelBookingWebView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, student=request.user)
        service = BookingService(actor=request.user)
        try:
            service.cancel_booking(booking)
            messages.success(request, "Вы отписались от лабораторной работы.")
        except BookingError as exc:
            messages.error(request, str(exc))
        return redirect("my-bookings")


class SupportListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/support.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return (
            SupportTicket.objects.filter(student=self.request.user)
            .select_related("training_center")
            .prefetch_related("messages__author")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.role == UserRole.STUDENT:
            ctx["training_centers"] = student_support_training_centers_qs(user)
        else:
            ctx["training_centers"] = TrainingCenter.objects.all()
        return ctx


class SupportCreateWebView(LoginRequiredMixin, View):
    def post(self, request):
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        tc_id = request.POST.get("training_center")
        if subject and body and tc_id:
            allowed_tc = student_support_training_centers_qs(request.user).filter(pk=tc_id).first()
            if not allowed_tc:
                messages.error(request, "Выбранная лаборатория недоступна для вашей группы.")
                return redirect("support")
            SupportTicket.objects.create(
                student=request.user,
                subject=subject,
                body=body,
                training_center=allowed_tc,
            )
            messages.success(request, "Обращение отправлено.")
        else:
            messages.error(request, "Заполните все поля, включая лабораторию.")
        return redirect("support")


class SupportDetailWebView(LoginRequiredMixin, View):
    template_name = "bookings/support_detail.html"

    def get(self, request, pk):
        ticket = get_object_or_404(
            SupportTicket.objects.prefetch_related("messages__author"),
            pk=pk,
            student=request.user,
        )
        return render(request, self.template_name, {"ticket": ticket})

    def post(self, request, pk):
        ticket = get_object_or_404(SupportTicket, pk=pk, student=request.user)
        body = request.POST.get("body", "").strip()
        if body:
            from apps.bookings.models import SupportMessage

            SupportMessage.objects.create(
                ticket=ticket,
                author=request.user,
                body=body,
            )
            messages.success(request, "Сообщение отправлено.")
        return redirect("support-detail", pk=pk)


class StaffBookingsWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/staff_bookings.html"
    context_object_name = "bookings"

    def dispatch(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            messages.error(request, "Доступ только для сотрудников лаборатории.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Booking.objects.select_related(
            "student",
            "student__profile",
            "lab_work",
            "discipline",
            "room",
            "room__training_center",
            "registered_by",
        )
        qs = staff_lab_filter(qs, self.request.user)
        qs = filter_staff_bookings(qs, self.request.GET)
        return qs.order_by("-scheduled_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filters"] = self.request.GET
        ctx["disciplines"] = staff_managed_disciplines_qs(self.request.user).filter(
            semester__is_active=True,
        )
        ctx["status_choices"] = Booking._meta.get_field("current_status").choices
        ctx["manual_lab_works"] = staff_managed_lab_works_qs(self.request.user).filter(
            discipline__semester__is_active=True,
            is_published=True,
        )
        return ctx


class StaffManualStudentSearchView(LoginRequiredMixin, View):
    def get(self, request):
        if not is_staff_user(request.user):
            return HttpResponseForbidden()
        query = request.GET.get("q", "").strip()
        students = search_students_for_staff(query)
        return render(
            request,
            "bookings/partials/staff_manual_student_results.html",
            {"students": students, "query": query},
        )


class StaffManualFilterPartialView(LoginRequiredMixin, View):
    """HTMX partial: календарный выбор слота для ручной записи (staff/lab scope)."""

    def get(self, request, lab_work_id):
        if not is_staff_user(request.user):
            return HttpResponseForbidden()
        get_object_or_404(staff_lab_works_qs(request.user), pk=lab_work_id)
        date = request.GET.get("date") or None
        time_str = request.GET.get("time") or None
        tc_number = request.GET.get("tc") or None
        room_id = request.GET.get("room") or None
        return _render_manual_filter_partial(
            request,
            lab_work_id,
            date,
            time_str,
            tc_number,
            room_id,
        )


class StaffManualBookingWebView(LoginRequiredMixin, View):
    def post(self, request):
        if not is_staff_user(request.user):
            return redirect("home")
        student_id = request.POST.get("student_id")
        session_id = request.POST.get("session_id")
        if not student_id:
            messages.error(request, "Выберите студента из результатов поиска.")
            return redirect("staff-bookings")
        student = User.objects.filter(pk=student_id, role=UserRole.STUDENT).first()
        if not student:
            messages.error(request, "Студент не найден.")
            return redirect("staff-bookings")
        if not session_id:
            messages.error(request, "Выберите слот для записи.")
            return redirect("staff-bookings")
        session = get_object_or_404(LabSession, pk=session_id)
        scoped = staff_lab_filter(
            LabSession.objects.filter(pk=session.pk),
            request.user,
        )
        if not scoped.exists():
            messages.error(request, "Слот недоступен для вашей лаборатории.")
            return redirect("staff-bookings")
        if not staff_lab_works_qs(request.user).filter(pk=session.lab_work_id).exists():
            messages.error(request, "Лабораторная работа недоступна для вашей лаборатории.")
            return redirect("staff-bookings")
        service = BookingService(actor=request.user)
        try:
            service.create_booking(student, int(session_id), manual=True, skip_student_rules=True)
            messages.success(request, f"Студент {student.full_name} записан вручную.")
        except BookingError as exc:
            messages.error(request, str(exc))
        return redirect("staff-bookings")


class StaffStatusUpdateWebView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not is_staff_user(request.user):
            return redirect("home")
        booking = get_object_or_404(Booking, pk=pk)
        scoped = staff_lab_filter(Booking.objects.filter(pk=booking.pk), request.user)
        if not scoped.exists():
            messages.error(request, "Запись недоступна для вашей лаборатории.")
            return redirect("staff-bookings")
        new_status = request.POST.get("status")
        service = BookingService(actor=request.user)
        try:
            service.change_status(booking, new_status)
            staff_status_labels = {
                BookingStatus.VISITED: "Посетил",
                BookingStatus.NO_SHOW: "Неявка",
                BookingStatus.REACCESS: "Повторный доступ",
                BookingStatus.CANCELLED: "Отмена записи",
            }
            label = staff_status_labels.get(new_status, new_status)
            messages.success(request, f"Статус изменён на «{label}».")
        except BookingError as exc:
            messages.error(request, str(exc))
        return redirect("staff-bookings")
