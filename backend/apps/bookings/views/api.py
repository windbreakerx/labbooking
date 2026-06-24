from django.conf import settings
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.querysets import (
    published_disciplines_qs,
    published_lab_works_qs,
    staff_can_access_lab_work,
    staff_disciplines_qs,
    staff_lab_works_qs,
    student_can_access_lab_work,
    student_disciplines_qs,
    student_lab_works_qs,
)
from apps.bookings.models import Booking, BookingStatus, SupportMessage, SupportTicket, WaitlistEntry
from apps.bookings.permissions import IsLabStaff, IsStudent
from apps.bookings.serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    BookingStatusSerializer,
    DisciplineDetailSerializer,
    DisciplineSerializer,
    LabSessionAdminSerializer,
    LabSessionSerializer,
    LabWorkSerializer,
    ManualBookingSerializer,
    SupportMessageSerializer,
    SupportTicketSerializer,
    WaitlistEntrySerializer,
)
from apps.bookings.services import BookingError, BookingService, is_staff_user, staff_can_access_scoped_object, staff_lab_filter
from apps.bookings.services.session_availability import (
    bookable_sessions_qs,
    get_session_filter_options,
)
from apps.scheduling.models import LabSession
from apps.users.models import UserRole


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class DisciplineListView(generics.ListAPIView):
    serializer_class = DisciplineSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.STUDENT:
            return student_disciplines_qs(user).select_related("semester")
        if is_staff_user(user):
            return staff_disciplines_qs(user).select_related("semester")
        return published_disciplines_qs().select_related("semester")


class DisciplineLabWorksView(generics.ListAPIView):
    serializer_class = LabWorkSerializer

    def get_queryset(self):
        user = self.request.user
        discipline_id = self.kwargs["pk"]
        if user.role == UserRole.STUDENT:
            if not student_disciplines_qs(user).filter(pk=discipline_id).exists():
                raise NotFound()
            return student_lab_works_qs(user, discipline_id=discipline_id)
        if is_staff_user(user):
            if not staff_disciplines_qs(user).filter(pk=discipline_id).exists():
                raise NotFound()
            return staff_lab_works_qs(user, discipline_id=discipline_id)
        return published_lab_works_qs(discipline_id)


class LabSessionListView(generics.ListAPIView):
    serializer_class = LabSessionSerializer

    def get_queryset(self):
        lab_work_id = self.request.query_params.get("lab_work")
        user = self.request.user
        if user.role == UserRole.STUDENT:
            accessible = student_lab_works_qs(user)
            if lab_work_id:
                if not accessible.filter(pk=int(lab_work_id)).exists():
                    return LabSession.objects.none()
                return bookable_sessions_qs(lab_work_id=int(lab_work_id), student=user)
            return bookable_sessions_qs(student=user).filter(lab_work__in=accessible)
        if is_staff_user(user):
            accessible = staff_lab_works_qs(user)
            qs = bookable_sessions_qs(lab_work_id=int(lab_work_id)) if lab_work_id else bookable_sessions_qs()
            if lab_work_id and not accessible.filter(pk=int(lab_work_id)).exists():
                return LabSession.objects.none()
            qs = qs.filter(lab_work__in=accessible) if not lab_work_id else qs
            return staff_lab_filter(qs, user)
        if lab_work_id:
            return bookable_sessions_qs(lab_work_id=int(lab_work_id))
        return bookable_sessions_qs()


class LabSessionFilterView(APIView):
    """Каскадные фильтры: date → time → training_center → room."""

    def get(self, request):
        lab_work = request.query_params.get("lab_work")
        if not lab_work:
            raise ValidationError({"lab_work": "Обязательный параметр."})
        if request.user.role == UserRole.STUDENT and not student_can_access_lab_work(
            request.user,
            int(lab_work),
        ):
            raise NotFound()
        if is_staff_user(request.user) and not staff_can_access_lab_work(
            request.user,
            int(lab_work),
        ):
            raise NotFound()
        data = get_session_filter_options(
            int(lab_work),
            date=request.query_params.get("date") or None,
            time_str=request.query_params.get("time") or None,
            tc_number=request.query_params.get("tc") or None,
            sessions_qs=bookable_sessions_qs(lab_work_id=int(lab_work), student=request.user)
            if request.user.role == UserRole.STUDENT
            else None,
        )
        return Response(data)


class LabSessionDetailView(generics.RetrieveAPIView):
    serializer_class = LabSessionSerializer

    def get_queryset(self):
        qs = LabSession.objects.select_related(
            "lab_work",
            "room",
            "room__training_center",
        )
        user = self.request.user
        if user.role == UserRole.STUDENT:
            return qs.filter(lab_work__in=student_lab_works_qs(user))
        if is_staff_user(user):
            return staff_lab_filter(qs.filter(lab_work__in=staff_lab_works_qs(user)), user)
        return qs


class MyBookingsView(generics.ListAPIView):
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(student=self.request.user)
            .select_related("lab_work", "discipline", "room", "room__training_center")
            .order_by("-scheduled_at")
        )


@method_decorator(ratelimit(key="user", rate="30/m", method="POST"), name="post")
class BookingCreateView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            booking = service.create_booking(
                request.user,
                serializer.validated_data["lab_session_id"],
            )
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingCancelView(APIView):
    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist as exc:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        if booking.student_id != request.user.id and not IsLabStaff().has_permission(request, self):
            return Response({"detail": "Нет доступа."}, status=status.HTTP_403_FORBIDDEN)
        if booking.student_id != request.user.id and not staff_can_access_scoped_object(
            request.user,
            Booking.objects.filter(pk=booking.pk),
        ):
            return Response({"detail": "Нет доступа."}, status=status.HTTP_403_FORBIDDEN)

        by_staff = booking.student_id != request.user.id
        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            booking = service.cancel_booking(booking, by_staff=by_staff)
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(BookingSerializer(booking).data)


class WaitlistJoinView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        session_id = request.data.get("lab_session_id")
        if not session_id:
            raise ValidationError({"lab_session_id": "Обязательное поле."})
        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            entry = service.join_waitlist(request.user, int(session_id))
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(WaitlistEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer

    def get_queryset(self):
        user = self.request.user
        if IsLabStaff().has_permission(self.request, self):
            qs = SupportTicket.objects.all().select_related("training_center").order_by("-created_at")
            return staff_lab_filter(qs, user, training_center_lookup="training_center")
        return SupportTicket.objects.filter(student=user).order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == UserRole.STUDENT:
            from apps.academics.querysets import student_support_training_centers_qs

            tc = serializer.validated_data.get("training_center")
            if tc and not student_support_training_centers_qs(user).filter(pk=tc.pk).exists():
                raise ValidationError({"training_center": "Лаборатория недоступна для вашей группы."})
        serializer.save(student=user)


class SupportMessageView(APIView):
    def post(self, request, ticket_id):
        try:
            ticket = SupportTicket.objects.get(pk=ticket_id)
        except SupportTicket.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        is_staff = IsLabStaff().has_permission(request, self)
        if ticket.student_id != request.user.id and not is_staff:
            return Response({"detail": "Нет доступа."}, status=status.HTTP_403_FORBIDDEN)
        if is_staff and not staff_can_access_scoped_object(
            request.user,
            SupportTicket.objects.filter(pk=ticket.pk),
            training_center_lookup="training_center",
        ):
            return Response({"detail": "Нет доступа."}, status=status.HTTP_403_FORBIDDEN)

        body = request.data.get("body", "").strip()
        if not body:
            raise ValidationError({"body": "Сообщение не может быть пустым."})

        msg = SupportMessage.objects.create(
            ticket=ticket,
            author=request.user,
            body=body,
        )
        if is_staff:
            ticket.status = SupportTicket.Status.ANSWERED
            ticket.save(update_fields=["status", "updated_at"])
        return Response(SupportMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class LabSessionAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsLabStaff]
    serializer_class = LabSessionAdminSerializer

    def get_queryset(self):
        qs = LabSession.objects.all().select_related("lab_work", "room", "semester", "teacher")
        return staff_lab_filter(qs, self.request.user)


class AdminBookingListView(generics.ListAPIView):
    permission_classes = [IsLabStaff]
    serializer_class = BookingSerializer

    def get_queryset(self):
        from django.db.models import Q

        qs = Booking.objects.select_related(
            "student",
            "lab_work",
            "discipline",
            "room",
            "room__training_center",
        )
        params = self.request.query_params
        if status_val := params.get("status"):
            qs = qs.filter(current_status=status_val)
        if discipline := params.get("discipline"):
            qs = qs.filter(discipline_id=discipline)
        if lab_work := params.get("lab_work"):
            qs = qs.filter(lab_work_id=lab_work)
        if student := params.get("student"):
            qs = qs.filter(
                Q(student__email__icontains=student)
                | Q(student__last_name__icontains=student)
            )
        return staff_lab_filter(qs, self.request.user).order_by("-scheduled_at")


class BookingStatusUpdateView(APIView):
    permission_classes = [IsLabStaff]

    def patch(self, request, pk):
        serializer = BookingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

        if not staff_can_access_scoped_object(
            request.user,
            Booking.objects.filter(pk=booking.pk),
        ):
            return Response({"detail": "Нет доступа."}, status=status.HTTP_403_FORBIDDEN)

        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            booking = service.change_status(
                booking,
                serializer.validated_data["status"],
                note=request.data.get("note", ""),
            )
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(BookingSerializer(booking).data)


class ManualBookingView(APIView):
    permission_classes = [IsLabStaff]

    def post(self, request):
        serializer = ManualBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.users.models import User

        try:
            student = User.objects.get(pk=serializer.validated_data["student_id"])
        except User.DoesNotExist:
            return Response({"detail": "Студент не найден."}, status=status.HTTP_404_NOT_FOUND)

        session_id = serializer.validated_data["lab_session_id"]
        if not staff_can_access_scoped_object(
            request.user,
            LabSession.objects.filter(pk=session_id),
        ):
            return Response({"detail": "Слот недоступен для вашей лаборатории."}, status=status.HTTP_403_FORBIDDEN)

        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            booking = service.create_booking(
                student,
                serializer.validated_data["lab_session_id"],
                manual=True,
                skip_student_rules=True,
            )
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class AdminReportView(APIView):
    permission_classes = [IsLabStaff]

    def get(self, request, report_type):
        from apps.bookings.reports import generate_report
        from django.http import HttpResponse

        content = generate_report(
            report_type,
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
            discipline_id=request.query_params.get("discipline"),
            staff_user=request.user,
        )
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{report_type}.xlsx"'
        return response
