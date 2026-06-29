from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.academics.querysets import (
    staff_managed_disciplines_qs,
    staff_managed_lab_works_qs,
    staff_people_qs,
)
from apps.bookings.models import SupportMessage, SupportTicket
from apps.bookings.reports import generate_report
from apps.bookings.services import is_staff_user, staff_lab_filter
from apps.scheduling.models import LabStand, ScheduleEntry
from apps.users.models import UserRole


class StaffRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not is_staff_user(request.user):
            messages.error(request, "Доступ только для сотрудников лаборатории.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


class StaffDisciplinesView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/disciplines.html"
    context_object_name = "disciplines"

    def get_queryset(self):
        return staff_managed_disciplines_qs(self.request.user)


class StaffLabWorksView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/lab_works.html"
    context_object_name = "lab_works"

    def get_queryset(self):
        return staff_managed_lab_works_qs(self.request.user).prefetch_related("disciplines")


class StaffLabWorkUploadView(StaffRequiredMixin, View):
    def post(self, request, pk):
        lab_work = get_object_or_404(staff_managed_lab_works_qs(request.user), pk=pk)
        if file := request.FILES.get("methodics_file"):
            if file.size > 10 * 1024 * 1024:
                messages.error(request, "Файл не должен превышать 10 МБ.")
            else:
                lab_work.methodics_file = file
                lab_work.save(update_fields=["methodics_file"])
                messages.success(request, "Методичка загружена.")
        return redirect("staff-lab-works")


class StaffRoomsView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/rooms.html"
    context_object_name = "rooms"

    def get_queryset(self):
        from apps.scheduling.models import Room

        qs = Room.objects.select_related("training_center", "laboratory").prefetch_related("disciplines").prefetch_related("disciplines")
        qs = staff_lab_filter(
            qs,
            self.request.user,
            training_center_lookup="training_center",
            laboratory_lookup="laboratory",
        )
        rooms = list(qs.order_by("number"))
        for room in rooms:
            room.room_disciplines = list(room.disciplines.order_by("title"))
        return rooms


class StaffStandsView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/stands.html"
    context_object_name = "stands"

    def get_queryset(self):
        qs = LabStand.objects.select_related("training_center", "room")
        return staff_lab_filter(qs, self.request.user, training_center_lookup="training_center")

    def get_context_data(self, **kwargs):
        from apps.scheduling.models import Room, TrainingCenter

        ctx = super().get_context_data(**kwargs)
        ctx["training_centers"] = staff_lab_filter(
            TrainingCenter.objects.all(),
            self.request.user,
            training_center_lookup="pk",
            laboratory_lookup=None,
        )
        ctx["rooms"] = staff_lab_filter(
            Room.objects.select_related("training_center"),
            self.request.user,
            training_center_lookup="training_center",
            laboratory_lookup="laboratory",
        )
        return ctx


class StaffStandCreateView(StaffRequiredMixin, View):
    def post(self, request):
        if request.user.role == UserRole.LAB_HEAD:
            return redirect("lab-head-stands")
        messages.error(request, "Добавление стендов доступно только заведующему лабораторией.")
        return redirect("staff-stands")


class StaffScheduleView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/schedule.html"
    context_object_name = "entries"

    def get_queryset(self):
        qs = ScheduleEntry.objects.select_related(
            "lab_work",
            "room",
            "semester",
            "teacher",
        ).prefetch_related("lab_work__disciplines")
        return staff_lab_filter(qs, self.request.user)


class StaffPeopleView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/people.html"
    context_object_name = "people"

    def get_queryset(self):
        return staff_people_qs(self.request.user)


class StaffSupportView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/support.html"
    context_object_name = "tickets"

    def get_queryset(self):
        qs = SupportTicket.objects.select_related(
            "student",
            "training_center",
        ).prefetch_related("messages__author")
        return staff_lab_filter(
            qs,
            self.request.user,
            training_center_lookup="training_center",
            laboratory_lookup=None,
        )


class StaffSupportReplyView(StaffRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(
            staff_lab_filter(
                SupportTicket.objects.all(),
                request.user,
                training_center_lookup="training_center",
                laboratory_lookup=None,
            ),
            pk=pk,
        )
        body = request.POST.get("body", "").strip()
        if body:
            SupportMessage.objects.create(
                ticket=ticket,
                author=request.user,
                body=body,
            )
            ticket.status = SupportTicket.Status.ANSWERED
            ticket.save(update_fields=["status", "updated_at"])
            messages.success(request, "Ответ отправлен.")
        return redirect("staff-support")


class StaffReportsView(StaffRequiredMixin, TemplateView):
    template_name = "bookings/staff/reports.html"


class StaffReportDownloadView(StaffRequiredMixin, View):
    def get(self, request, report_type):
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        discipline_id = request.GET.get("discipline")
        content = generate_report(
            report_type,
            date_from=date_from,
            date_to=date_to,
            discipline_id=discipline_id,
            staff_user=request.user,
        )
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{report_type}.xlsx"'
        return response
