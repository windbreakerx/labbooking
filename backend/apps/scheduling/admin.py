from django.contrib import admin

from .models import Holiday, LabSession, LabStand, Room, ScheduleEntry, TrainingCenter


@admin.register(TrainingCenter)
class TrainingCenterAdmin(admin.ModelAdmin):
    list_display = ("number", "name")
    search_fields = ("number", "name")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "training_center", "capacity")
    list_filter = ("training_center",)


@admin.register(LabSession)
class LabSessionAdmin(admin.ModelAdmin):
    list_display = ("lab_work", "room", "starts_at", "capacity", "status")
    list_filter = ("status", "semester", "room__training_center")
    date_hierarchy = "starts_at"
    search_fields = ("lab_work__title",)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")


@admin.register(LabStand)
class LabStandAdmin(admin.ModelAdmin):
    list_display = ("name", "inventory_number", "training_center", "room")
    list_filter = ("training_center",)


@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ("lab_work", "room", "weekday", "start_time", "week_parity", "is_active")
    list_filter = ("semester", "week_parity", "is_active")
