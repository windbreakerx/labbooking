from django.contrib import admin

from .models import Holiday, LabSession, Room, TrainingCenter


@admin.register(TrainingCenter)
class TrainingCenterAdmin(admin.ModelAdmin):
    list_display = ("number", "name")


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
