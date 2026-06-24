from rest_framework import serializers

from apps.academics.models import Discipline, LabWork
from apps.bookings.models import Booking, SupportMessage, SupportTicket, WaitlistEntry
from apps.scheduling.models import LabSession, Room, TrainingCenter


class TrainingCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingCenter
        fields = ("id", "number", "name")


class RoomSerializer(serializers.ModelSerializer):
    training_center = TrainingCenterSerializer(read_only=True)

    class Meta:
        model = Room
        fields = ("id", "number", "capacity", "training_center")


class LabWorkSerializer(serializers.ModelSerializer):
    primary_stand_id = serializers.IntegerField(source="primary_stand_id", read_only=True)

    class Meta:
        model = LabWork
        fields = ("id", "number", "title", "description", "duration_minutes", "capacity", "primary_stand_id")


class DisciplineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ("id", "title", "description")


class DisciplineDetailSerializer(DisciplineSerializer):
    lab_works = LabWorkSerializer(many=True, read_only=True)

    class Meta(DisciplineSerializer.Meta):
        fields = DisciplineSerializer.Meta.fields + ("lab_works",)


class LabSessionSerializer(serializers.ModelSerializer):
    lab_work = LabWorkSerializer(read_only=True)
    room = RoomSerializer(read_only=True)
    available_seats = serializers.IntegerField(read_only=True)
    booked_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = LabSession
        fields = (
            "id",
            "lab_work",
            "room",
            "starts_at",
            "ends_at",
            "capacity",
            "status",
            "available_seats",
            "booked_count",
        )


class BookingSerializer(serializers.ModelSerializer):
    lab_work_title = serializers.CharField(source="lab_work.title", read_only=True)
    discipline_title = serializers.CharField(source="discipline.title", read_only=True)
    room_number = serializers.CharField(source="room.number", read_only=True)
    training_center_number = serializers.IntegerField(
        source="room.training_center.number",
        read_only=True,
    )

    class Meta:
        model = Booking
        fields = (
            "id",
            "lab_work_title",
            "discipline_title",
            "room_number",
            "training_center_number",
            "scheduled_at",
            "current_status",
            "registration_type",
            "created_at",
        )
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    lab_session_id = serializers.IntegerField()


class BookingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking._meta.get_field("current_status").choices)


class ManualBookingSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    lab_session_id = serializers.IntegerField()


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = (
            "id",
            "subject",
            "body",
            "status",
            "training_center",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "created_at", "updated_at")


class SupportMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)

    class Meta:
        model = SupportMessage
        fields = ("id", "body", "author_name", "created_at")
        read_only_fields = fields


class WaitlistEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitlistEntry
        fields = ("id", "lab_session", "position", "created_at")
        read_only_fields = fields


class LabSessionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabSession
        fields = (
            "id",
            "lab_work",
            "room",
            "semester",
            "teacher",
            "starts_at",
            "ends_at",
            "capacity",
            "status",
        )
