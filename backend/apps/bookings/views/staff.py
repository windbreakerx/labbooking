from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.academics.querysets import (
    staff_managed_disciplines_qs,
    staff_managed_lab_works_qs,
)
from apps.bookings.models import SupportMessage, SupportTicket
from apps.bookings.reports import generate_report
from apps.bookings.services import is_staff_user, staff_lab_filter
from apps.scheduling.models import LabStand, ScheduleEntry
from apps.users.models import User, UserRole


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
        return staff_managed_lab_works_qs(self.request.user)


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
        )
        ctx["rooms"] = staff_lab_filter(
            Room.objects.select_related("training_center"),
            self.request.user,
            training_center_lookup="training_center",
        )
        return ctx


class StaffStandCreateView(StaffRequiredMixin, View):
    def post(self, request):
        from apps.scheduling.models import Room, TrainingCenter

        name = request.POST.get("name", "").strip()
        inv = request.POST.get("inventory_number", "").strip()
        tc_id = request.POST.get("training_center")
        room_id = request.POST.get("room")
        if name and inv and tc_id and room_id:
            tc = staff_lab_filter(
                TrainingCenter.objects.filter(pk=tc_id),
                request.user,
                training_center_lookup="pk",
            ).first()
            room = staff_lab_filter(
                Room.objects.filter(pk=room_id),
                request.user,
                training_center_lookup="training_center",
            ).first()
            if not tc or not room:
                messages.error(request, "Лаборатория или аудитория недоступны.")
                return redirect("staff-stands")
            LabStand.objects.create(
                name=name,
                inventory_number=inv,
                training_center=tc,
                room=room,
                description=request.POST.get("description", ""),
            )
            messages.success(request, "Стенд добавлен.")
        else:
            messages.error(request, "Заполните обязательные поля.")
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
        )
        return staff_lab_filter(qs, self.request.user)


class StaffPeopleView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/people.html"
    context_object_name = "people"

    def get_queryset(self):
        return User.objects.filter(
            role__in=[UserRole.TEACHER, UserRole.LAB_ADMIN],
        ).select_related("profile")


class StaffSupportView(StaffRequiredMixin, ListView):
    template_name = "bookings/staff/support.html"
    context_object_name = "tickets"

    def get_queryset(self):
        qs = SupportTicket.objects.select_related(
            "student",
            "training_center",
        ).prefetch_related("messages__author")
        return staff_lab_filter(qs, self.request.user, training_center_lookup="training_center")


class StaffSupportReplyView(StaffRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(
            staff_lab_filter(
                SupportTicket.objects.all(),
                request.user,
                training_center_lookup="training_center",
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
