from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Discipline, LabWork
from apps.bookings.models import Booking, BookingStatus, SupportTicket
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
    SupportTicketSerializer,
)
from apps.bookings.services import BookingError, BookingService
from apps.scheduling.models import LabSession, LabSessionStatus


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class DisciplineListView(generics.ListAPIView):
    serializer_class = DisciplineSerializer

    def get_queryset(self):
        return Discipline.objects.filter(is_published=True).select_related("semester")


class DisciplineLabWorksView(generics.ListAPIView):
    serializer_class = LabWorkSerializer

    def get_queryset(self):
        return LabWork.objects.filter(
            discipline_id=self.kwargs["pk"],
            is_published=True,
        )


class LabSessionListView(generics.ListAPIView):
    serializer_class = LabSessionSerializer

    def get_queryset(self):
        now = timezone.now()
        horizon = now + timezone.timedelta(days=settings.BOOKING_HORIZON_DAYS)
        qs = (
            LabSession.objects.filter(
                status=LabSessionStatus.OPEN,
                starts_at__gt=now,
                starts_at__lte=horizon,
            )
            .select_related("lab_work", "room", "room__training_center")
            .order_by("starts_at")
        )
        lab_work_id = self.request.query_params.get("lab_work")
        if lab_work_id:
            qs = qs.filter(lab_work_id=lab_work_id)
        return qs


class LabSessionDetailView(generics.RetrieveAPIView):
    serializer_class = LabSessionSerializer
    queryset = LabSession.objects.select_related(
        "lab_work",
        "room",
        "room__training_center",
    )


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

        by_staff = booking.student_id != request.user.id
        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            booking = service.cancel_booking(booking, by_staff=by_staff)
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(BookingSerializer(booking).data)


class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer

    def get_queryset(self):
        user = self.request.user
        if IsLabStaff().has_permission(self.request, self):
            return SupportTicket.objects.all().order_by("-created_at")
        return SupportTicket.objects.filter(student=user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class LabSessionAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsLabStaff]
    serializer_class = LabSessionAdminSerializer
    queryset = LabSession.objects.all().select_related("lab_work", "room", "semester", "teacher")


class AdminBookingListView(generics.ListAPIView):
    permission_classes = [IsLabStaff]
    serializer_class = BookingSerializer

    def get_queryset(self):
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
        return qs.order_by("-scheduled_at")


class BookingStatusUpdateView(APIView):
    permission_classes = [IsLabStaff]

    def patch(self, request, pk):
        serializer = BookingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = Booking.objects.get(pk=pk)
        except Booking.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)

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

        service = BookingService(actor=request.user, ip_address=get_client_ip(request))
        try:
            booking = service.create_booking(
                student,
                serializer.validated_data["lab_session_id"],
                manual=True,
            )
        except BookingError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)
