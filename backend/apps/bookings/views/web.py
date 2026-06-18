import calendar
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.academics.models import Discipline, LabWork
from apps.academics.querysets import published_disciplines_qs, published_lab_works_qs
from apps.bookings.models import Booking, SupportTicket
from apps.bookings.services import (
    BookingError,
    BookingService,
    filter_staff_bookings,
    is_staff_user,
    staff_lab_filter,
)
from apps.bookings.services.session_availability import (
    get_session_filter_options,
    get_sessions_for_selection,
)
from apps.scheduling.models import LabSession, LabSessionStatus, TrainingCenter
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

    month_keys = sorted({(d.year, d.month) for d in parsed_dates})
    months = []
    for year, month in month_keys:
        month_calendar = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        weeks = []
        for week in month_calendar:
            cells = []
            for day in week:
                option = option_by_date.get(day)
                cells.append(
                    {
                        "day": day.day,
                        "is_current_month": day.month == month,
                        "is_available": bool(option),
                        "value": option.get("value") if option else "",
                        "label": option.get("label") if option else "",
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


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "bookings/home.html"


class DisciplineListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/disciplines.html"
    context_object_name = "disciplines"

    def get_queryset(self):
        return published_disciplines_qs()


class LabWorkListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/lab_works.html"
    context_object_name = "lab_works"

    def get_queryset(self):
        return published_lab_works_qs(self.kwargs["discipline_id"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["discipline"] = get_object_or_404(
            published_disciplines_qs(),
            pk=self.kwargs["discipline_id"],
        )
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
            LabWork,
            pk=lab_work_id,
            is_published=True,
            discipline__semester__is_active=True,
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
        get_object_or_404(LabWork, pk=lab_work_id, is_published=True)
        date = request.GET.get("date") or None
        time_str = request.GET.get("time") or None
        tc_number = request.GET.get("tc") or None
        room_id = request.GET.get("room") or None

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
        ctx["training_centers"] = TrainingCenter.objects.all()
        return ctx


class SupportCreateWebView(LoginRequiredMixin, View):
    def post(self, request):
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        tc_id = request.POST.get("training_center")
        if subject and body and tc_id:
            SupportTicket.objects.create(
                student=request.user,
                subject=subject,
                body=body,
                training_center_id=tc_id,
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
        ctx["disciplines"] = Discipline.objects.filter(
            semester__is_active=True,
        ).order_by("title")
        ctx["status_choices"] = Booking._meta.get_field("current_status").choices
        sessions_qs = LabSession.objects.filter(
            status=LabSessionStatus.OPEN,
            starts_at__gt=timezone.now(),
        ).select_related("lab_work", "room", "room__training_center")
        ctx["manual_sessions"] = staff_lab_filter(
            sessions_qs,
            self.request.user,
        ).order_by("starts_at")[:200]
        return ctx


class StaffManualBookingWebView(LoginRequiredMixin, View):
    def post(self, request):
        if not is_staff_user(request.user):
            return redirect("home")
        student_email = request.POST.get("student_email", "").strip().lower()
        session_id = request.POST.get("session_id")
        student = User.objects.filter(email__iexact=student_email, role=UserRole.STUDENT).first()
        if not student:
            messages.error(request, "Студент с таким email не найден.")
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
            messages.success(request, f"Статус изменён на «{new_status}».")
        except BookingError as exc:
            messages.error(request, str(exc))
        return redirect("staff-bookings")
