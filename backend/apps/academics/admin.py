from django.contrib import admin

from .models import Discipline, LabWork, Semester


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "semester", "is_published")
    list_filter = ("semester", "is_published")
    search_fields = ("title", "code")


@admin.register(LabWork)
class LabWorkAdmin(admin.ModelAdmin):
    list_display = ("title", "discipline", "number", "duration_minutes", "is_published")
    list_filter = ("discipline", "is_published")
    search_fields = ("title",)
