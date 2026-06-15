from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.academics.models import Discipline, LabWork
from apps.bookings.models import Booking, SupportTicket
from apps.bookings.services import BookingError, BookingService, is_staff_user
from apps.scheduling.models import LabSession, LabSessionStatus


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "bookings/home.html"


class DisciplineListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/disciplines.html"
    context_object_name = "disciplines"

    def get_queryset(self):
        return Discipline.objects.filter(is_published=True)


class LabWorkListWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/lab_works.html"
    context_object_name = "lab_works"

    def get_queryset(self):
        return LabWork.objects.filter(
            discipline_id=self.kwargs["discipline_id"],
            is_published=True,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["discipline"] = get_object_or_404(Discipline, pk=self.kwargs["discipline_id"])
        return ctx


class BookLabWorkWebView(LoginRequiredMixin, View):
    template_name = "bookings/book.html"

    def get(self, request, lab_work_id):
        lab_work = get_object_or_404(LabWork, pk=lab_work_id, is_published=True)
        sessions = LabSession.objects.filter(
            lab_work=lab_work,
            status=LabSessionStatus.OPEN,
        ).select_related("room", "room__training_center")
        return render(
            request,
            self.template_name,
            {"lab_work": lab_work, "sessions": sessions},
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
        return SupportTicket.objects.filter(student=self.request.user)


class SupportCreateWebView(LoginRequiredMixin, View):
    def post(self, request):
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        if subject and body:
            SupportTicket.objects.create(student=request.user, subject=subject, body=body)
            messages.success(request, "Обращение отправлено.")
        else:
            messages.error(request, "Заполните тему и сообщение.")
        return redirect("support")


class StaffBookingsWebView(LoginRequiredMixin, ListView):
    template_name = "bookings/staff_bookings.html"
    context_object_name = "bookings"

    def dispatch(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            messages.error(request, "Доступ только для сотрудников лаборатории.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Booking.objects.select_related(
            "student",
            "lab_work",
            "discipline",
            "room",
        ).order_by("-scheduled_at")


class StaffStatusUpdateWebView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not is_staff_user(request.user):
            return redirect("home")
        booking = get_object_or_404(Booking, pk=pk)
        new_status = request.POST.get("status")
        service = BookingService(actor=request.user)
        try:
            service.change_status(booking, new_status)
            messages.success(request, f"Статус изменён на «{new_status}».")
        except BookingError as exc:
            messages.error(request, str(exc))
        return redirect("staff-bookings")
