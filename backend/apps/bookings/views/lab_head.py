from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.academics.models import LabWork
from apps.academics.querysets import staff_managed_disciplines_qs, staff_managed_lab_works_qs
from apps.bookings.services.lab_head import (
    is_lab_head_user,
    lab_head_active_semester,
    filter_lab_head_lab_works,
    filter_lab_head_stands,
    lab_head_bindable_disciplines_qs,
    lab_head_bindable_lab_works_qs,
    lab_head_discipline_in_scope,
    lab_head_lab_work_in_scope,
    lab_head_laboratories_qs,
    lab_head_laboratory,
    lab_head_laboratory_in_scope,
    lab_head_people_qs,
    lab_head_room_in_scope,
    lab_head_rooms_qs,
    lab_head_schedule_qs,
    lab_head_teachers_qs,
    lab_head_training_center,
    lab_head_training_center_in_scope,
    lab_head_training_centers_qs,
    lab_head_update_lab_work,
    sync_training_centers_for_laboratories,
)
from apps.scheduling.models import LabStand, ScheduleEntry, WeekParity
from apps.users.models import User, UserRole

WEEKDAY_LABELS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


class LabHeadRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not is_lab_head_user(request.user):
            messages.error(request, "Доступ только для заведующего лабораторией.")
            return redirect("home")
        if not lab_head_training_center(request.user):
            messages.error(request, "В профиле не указана лаборатория.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_training_center(self):
        return lab_head_training_center(self.request.user)


class LabHeadHomeView(LabHeadRequiredMixin, TemplateView):
    template_name = "bookings/lab_head/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tc = self.get_training_center()
        ctx["training_center"] = tc
        ctx["people_count"] = lab_head_people_qs(self.request.user).count()
        ctx["disciplines_count"] = staff_managed_disciplines_qs(self.request.user).count()
        ctx["lab_works_count"] = staff_managed_lab_works_qs(self.request.user).count()
        ctx["stands_count"] = LabStand.objects.filter(training_center=tc).count()
        ctx["schedule_count"] = lab_head_schedule_qs(self.request.user).count()
        return ctx


class LabHeadPeopleView(LabHeadRequiredMixin, ListView):
    template_name = "bookings/lab_head/people.html"
    context_object_name = "people"

    def get_queryset(self):
        return lab_head_people_qs(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["training_center"] = self.get_training_center()
        ctx["lab_disciplines"] = staff_managed_disciplines_qs(self.request.user)
        ctx["role_choices"] = [
            (UserRole.LAB_ADMIN, UserRole.LAB_ADMIN.label),
            (UserRole.TEACHER, UserRole.TEACHER.label),
        ]
        return ctx


class LabHeadPersonCreateView(LabHeadRequiredMixin, View):
    def post(self, request):
        tc = self.get_training_center()
        email = request.POST.get("email", "").strip().lower()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        role = request.POST.get("role", "")
        password = request.POST.get("password", "").strip() or "ChangeMe123!"

        if not email or not first_name or not last_name:
            messages.error(request, "Заполните email, имя и фамилию.")
            return redirect("lab-head-people")
        if role not in {UserRole.LAB_ADMIN, UserRole.TEACHER}:
            messages.error(request, "Выберите роль: сотрудник или преподаватель.")
            return redirect("lab-head-people")
        if User.objects.filter(email=email).exists():
            messages.error(request, "Пользователь с таким email уже существует.")
            return redirect("lab-head-people")

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_staff=(role == UserRole.LAB_ADMIN),
        )
        user.profile.training_center = tc
        user.profile.save(update_fields=["training_center"])
        messages.success(
            request,
            f"Добавлен {user.get_role_display()}: {user.full_name}. Временный пароль: {password}",
        )
        return redirect("lab-head-people")


class LabHeadPersonBindingsView(LabHeadRequiredMixin, View):
    def post(self, request, pk):
        person = get_object_or_404(lab_head_people_qs(request.user), pk=pk)
        discipline_ids = request.POST.getlist("disciplines")
        allowed_ids = set(
            staff_managed_disciplines_qs(request.user).filter(pk__in=discipline_ids).values_list("pk", flat=True)
        )
        person.profile.disciplines.set(allowed_ids)
        messages.success(request, f"Привязки дисциплин для {person.full_name} обновлены.")
        return redirect("lab-head-people")


class LabHeadBindingsView(LabHeadRequiredMixin, TemplateView):
    template_name = "bookings/lab_head/bindings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        managed_lab_works = staff_managed_lab_works_qs(user)
        bindable_lab_works = list(lab_head_bindable_lab_works_qs(user))
        bindable_by_discipline: dict[int, list] = {}
        for lab_work in bindable_lab_works:
            bindable_by_discipline.setdefault(lab_work.discipline_id, []).append(lab_work)

        lab_disciplines = list(
            staff_managed_disciplines_qs(user)
            .select_related("semester")
            .prefetch_related(
                Prefetch(
                    "lab_works",
                    queryset=managed_lab_works,
                    to_attr="managed_lab_works",
                )
            )
        )
        for discipline in lab_disciplines:
            discipline.bindable_lab_works = bindable_by_discipline.get(discipline.pk, [])

        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            lab_disciplines = [d for d in lab_disciplines if search_query.lower() in d.title.lower()]
            bindable_disciplines = lab_head_bindable_disciplines_qs(user).filter(title__icontains=search_query)
        else:
            bindable_disciplines = lab_head_bindable_disciplines_qs(user)

        ctx["training_center"] = self.get_training_center()
        ctx["laboratory"] = lab_head_laboratory(user)
        ctx["lab_disciplines"] = lab_disciplines
        ctx["bindable_disciplines"] = bindable_disciplines
        ctx["search_query"] = search_query
        return ctx


class LabHeadDisciplineCreateView(LabHeadRequiredMixin, View):
    def post(self, request):
        messages.error(request, "Создание дисциплин доступно только в админке.")
        return redirect("lab-head-bindings")


class LabHeadDisciplineBindView(LabHeadRequiredMixin, View):
    def post(self, request, pk):
        laboratory = lab_head_laboratory(request.user)
        discipline = get_object_or_404(
            lab_head_bindable_disciplines_qs(request.user),
            pk=pk,
        )
        if not laboratory:
            messages.error(request, "Лаборатория не указана.")
            return redirect("lab-head-bindings")
        discipline.laboratories.add(laboratory)
        sync_training_centers_for_laboratories(discipline)
        messages.success(request, f"Дисциплина «{discipline.title}» привязана к лаборатории.")
        return redirect("lab-head-bindings")


class LabHeadDisciplineUnbindView(LabHeadRequiredMixin, View):
    def post(self, request, pk):
        laboratory = lab_head_laboratory(request.user)
        discipline = lab_head_discipline_in_scope(request.user, pk)
        if not discipline:
            messages.error(request, "Дисциплина недоступна.")
            return redirect("lab-head-bindings")
        if not laboratory:
            messages.error(request, "Лаборатория не указана.")
            return redirect("lab-head-bindings")
        discipline.laboratories.remove(laboratory)
        sync_training_centers_for_laboratories(discipline)
        messages.success(request, f"Дисциплина «{discipline.title}» отвязана от лаборатории.")
        return redirect("lab-head-bindings")


class LabHeadLabWorkBindView(LabHeadRequiredMixin, View):
    def post(self, request, pk):
        laboratory = lab_head_laboratory(request.user)
        lab_work = get_object_or_404(lab_head_bindable_lab_works_qs(request.user), pk=pk)
        if not laboratory:
            messages.error(request, "Лаборатория не указана.")
            return redirect("lab-head-bindings")
        lab_work.laboratories.add(laboratory)
        sync_training_centers_for_laboratories(lab_work)
        messages.success(request, f"ЛР «{lab_work.title}» привязана к лаборатории.")
        return redirect("lab-head-bindings")


class LabHeadLabWorkUnbindView(LabHeadRequiredMixin, View):
    def post(self, request, pk):
        laboratory = lab_head_laboratory(request.user)
        lab_work = lab_head_lab_work_in_scope(request.user, pk)
        if not lab_work:
            messages.error(request, "Лабораторная работа недоступна.")
            return redirect("lab-head-bindings")
        if not laboratory:
            messages.error(request, "Лаборатория не указана.")
            return redirect("lab-head-bindings")
        lab_work.laboratories.remove(laboratory)
        sync_training_centers_for_laboratories(lab_work)
        messages.success(request, f"ЛР «{lab_work.title}» отвязана от лаборатории.")
        return redirect("lab-head-bindings")


class LabHeadLabWorksView(LabHeadRequiredMixin, ListView):
    template_name = "bookings/lab_head/lab_works.html"
    context_object_name = "lab_works"

    def get_queryset(self):
        qs = (
            staff_managed_lab_works_qs(self.request.user)
            .select_related("discipline", "default_room", "default_room__training_center")
            .prefetch_related("training_centers", "laboratories", "laboratories__training_center")
        )
        return filter_lab_head_lab_works(qs, self.request.GET.get("q", ""))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["training_center"] = self.get_training_center()
        ctx["laboratory"] = lab_head_laboratory(self.request.user)
        ctx["lab_disciplines"] = staff_managed_disciplines_qs(self.request.user)
        ctx["training_centers"] = lab_head_training_centers_qs(self.request.user)
        ctx["laboratories"] = lab_head_laboratories_qs(self.request.user)
        ctx["rooms"] = lab_head_rooms_qs(self.request.user)
        ctx["edit_lab_work_id"] = self.request.GET.get("edit", "").strip()
        ctx["search_query"] = self.request.GET.get("q", "").strip()
        return ctx


class LabHeadLabWorkCreateView(LabHeadRequiredMixin, View):
    def post(self, request):
        discipline_id = request.POST.get("discipline")
        laboratory_id = request.POST.get("laboratory", "").strip()
        room_id = request.POST.get("default_room", "").strip()
        number = request.POST.get("number", "").strip()
        title = request.POST.get("title", "").strip()
        duration = request.POST.get("duration_minutes", "").strip() or "90"
        capacity = request.POST.get("capacity", "").strip() or "30"

        discipline = lab_head_discipline_in_scope(request.user, int(discipline_id)) if discipline_id else None
        laboratory = lab_head_laboratory_in_scope(request.user, int(laboratory_id)) if laboratory_id else None
        default_room = lab_head_room_in_scope(request.user, int(room_id)) if room_id else None

        if not discipline or not laboratory or not number or not title:
            messages.error(request, "Заполните дисциплину, лабораторию, номер и название ЛР.")
            return redirect("lab-head-lab-works")
        if room_id and not default_room:
            messages.error(request, "Выбранная аудитория недоступна.")
            return redirect("lab-head-lab-works")
        if default_room and default_room.training_center_id != laboratory.training_center_id:
            messages.error(request, "Аудитория должна относиться к учебному центру лаборатории.")
            return redirect("lab-head-lab-works")

        try:
            number_int = int(number)
            duration_int = int(duration)
            capacity_int = int(capacity)
        except ValueError:
            messages.error(request, "Номер, длительность и места должны быть числами.")
            return redirect("lab-head-lab-works")

        if capacity_int < 1:
            messages.error(request, "Количество мест должно быть не меньше 1.")
            return redirect("lab-head-lab-works")

        if LabWork.objects.filter(discipline=discipline, number=number_int).exists():
            messages.error(request, f"ЛР №{number_int} для этой дисциплины уже существует.")
            return redirect("lab-head-lab-works")

        lab_work = LabWork.objects.create(
            discipline=discipline,
            number=number_int,
            title=title,
            duration_minutes=duration_int,
            capacity=capacity_int,
            is_published=True,
            default_room=default_room,
        )
        lab_work.laboratories.set([laboratory.pk])
        sync_training_centers_for_laboratories(lab_work)
        messages.success(request, f"Лабораторная работа «{lab_work.title}» добавлена.")
        return redirect("lab-head-lab-works")


class LabHeadLabWorkUpdateView(LabHeadRequiredMixin, View):
    def post(self, request, pk):
        lab_work = lab_head_lab_work_in_scope(request.user, pk)
        if not lab_work:
            messages.error(request, "Лабораторная работа недоступна.")
            return redirect("lab-head-lab-works")

        discipline_id = request.POST.get("discipline", "").strip()
        laboratory_id = request.POST.get("laboratory", "").strip()
        room_id = request.POST.get("default_room", "").strip()
        discipline = lab_head_discipline_in_scope(request.user, int(discipline_id)) if discipline_id else None
        laboratory = lab_head_laboratory_in_scope(request.user, int(laboratory_id)) if laboratory_id else None
        default_room = lab_head_room_in_scope(request.user, int(room_id)) if room_id else None
        title = request.POST.get("title", "").strip()
        number = request.POST.get("number", "").strip()
        duration = request.POST.get("duration_minutes", "").strip()
        capacity = request.POST.get("capacity", "").strip()
        is_published = request.POST.get("is_published") == "on"

        if not discipline or not laboratory or not title or not number or not duration or not capacity:
            messages.error(request, "Заполните все обязательные поля лабораторной работы.")
            return redirect("lab-head-lab-works")
        if room_id and not default_room:
            messages.error(request, "Выбранная аудитория недоступна.")
            return redirect("lab-head-lab-works")

        try:
            number_int = int(number)
            duration_int = int(duration)
            capacity_int = int(capacity)
        except ValueError:
            messages.error(request, "Номер, длительность и места должны быть числами.")
            return redirect("lab-head-lab-works")

        try:
            lab_head_update_lab_work(
                request.user,
                lab_work,
                title=title,
                number=number_int,
                discipline=discipline,
                duration_minutes=duration_int,
                capacity=capacity_int,
                is_published=is_published,
                laboratory=laboratory,
                default_room=default_room,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("lab-head-lab-works")

        messages.success(request, f"Лабораторная работа «{lab_work.title}» обновлена.")
        return redirect("lab-head-lab-works")


class LabHeadStandsView(LabHeadRequiredMixin, ListView):
    template_name = "bookings/lab_head/stands.html"
    context_object_name = "stands"

    def get_queryset(self):
        tc = self.get_training_center()
        qs = LabStand.objects.filter(training_center=tc).select_related("training_center", "room")
        return filter_lab_head_stands(qs, self.request.GET.get("q", ""))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["training_center"] = self.get_training_center()
        ctx["rooms"] = lab_head_rooms_qs(self.request.user)
        ctx["search_query"] = self.request.GET.get("q", "").strip()
        return ctx


class LabHeadStandCreateView(LabHeadRequiredMixin, View):
    def post(self, request):
        tc = self.get_training_center()
        name = request.POST.get("name", "").strip()
        inv = request.POST.get("inventory_number", "").strip()
        room_id = request.POST.get("room")

        room = lab_head_rooms_qs(request.user).filter(pk=room_id).first()
        if not name or not inv or not room:
            messages.error(request, "Заполните название, инв. номер и аудиторию.")
            return redirect("lab-head-stands")

        LabStand.objects.create(
            name=name,
            inventory_number=inv,
            training_center=tc,
            room=room,
            description=request.POST.get("description", ""),
        )
        messages.success(request, "Стенд добавлен.")
        return redirect("lab-head-stands")


class LabHeadScheduleView(LabHeadRequiredMixin, ListView):
    template_name = "bookings/lab_head/schedule.html"
    context_object_name = "entries"

    def get_queryset(self):
        return lab_head_schedule_qs(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["training_center"] = self.get_training_center()
        ctx["lab_works"] = staff_managed_lab_works_qs(self.request.user)
        ctx["rooms"] = lab_head_rooms_qs(self.request.user)
        ctx["teachers"] = lab_head_teachers_qs(self.request.user)
        ctx["weekday_labels"] = WEEKDAY_LABELS
        ctx["week_parity_choices"] = WeekParity.choices
        ctx["active_semester"] = lab_head_active_semester()
        ctx["schedule_rows"] = [
            {
                "entry": entry,
                "weekday_label": WEEKDAY_LABELS[entry.weekday]
                if 0 <= entry.weekday < len(WEEKDAY_LABELS)
                else str(entry.weekday),
            }
            for entry in ctx["entries"]
        ]
        return ctx


class LabHeadScheduleCreateView(LabHeadRequiredMixin, View):
    def post(self, request):
        semester = lab_head_active_semester()
        if not semester:
            messages.error(request, "Нет активного семестра.")
            return redirect("lab-head-schedule")

        lab_work_id = request.POST.get("lab_work")
        lab_work = lab_head_lab_work_in_scope(request.user, int(lab_work_id)) if lab_work_id else None
        room = lab_head_rooms_qs(request.user).filter(pk=request.POST.get("room")).first()
        teacher = None
        teacher_id = request.POST.get("teacher", "").strip()
        if teacher_id:
            teacher = lab_head_teachers_qs(request.user).filter(pk=teacher_id).first()
            if not teacher:
                messages.error(request, "Преподаватель недоступен.")
                return redirect("lab-head-schedule")

        weekday = request.POST.get("weekday", "").strip()
        start_time_raw = request.POST.get("start_time", "").strip()
        week_parity = request.POST.get("week_parity", WeekParity.BOTH)
        capacity = request.POST.get("capacity", "").strip() or "30"
        duration = request.POST.get("duration_minutes", "").strip() or "90"

        if not lab_work or not room or not start_time_raw or weekday == "":
            messages.error(request, "Заполните ЛР, аудиторию, день недели и время.")
            return redirect("lab-head-schedule")

        try:
            weekday_int = int(weekday)
            capacity_int = int(capacity)
            duration_int = int(duration)
            start_time = datetime.strptime(start_time_raw, "%H:%M").time()
        except ValueError:
            messages.error(request, "Проверьте день недели, время, места и длительность.")
            return redirect("lab-head-schedule")

        if week_parity not in WeekParity.values:
            week_parity = WeekParity.BOTH

        ScheduleEntry.objects.create(
            lab_work=lab_work,
            room=room,
            semester=semester,
            week_parity=week_parity,
            weekday=weekday_int,
            start_time=start_time,
            duration_minutes=duration_int,
            capacity=capacity_int,
            teacher=teacher,
            is_active=True,
        )
        messages.success(request, "Запись расписания добавлена.")
        return redirect("lab-head-schedule")
