from django.contrib import admin

from .models import Discipline, LabWork, Semester, StudentGroup


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty", "dekanat_id")
    search_fields = ("name", "faculty", "dekanat_id")
    list_filter = ("faculty",)
    filter_horizontal = ("disciplines", "lab_works")


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "semester", "is_published")
    list_filter = ("semester", "is_published", "training_centers")
    search_fields = ("title", "code")
    filter_horizontal = ("training_centers",)


@admin.register(LabWork)
class LabWorkAdmin(admin.ModelAdmin):
    list_display = ("title", "discipline", "number", "duration_minutes", "capacity", "primary_stand", "is_published")
    list_filter = ("discipline", "is_published", "training_centers")
    search_fields = ("title",)
    filter_horizontal = ("training_centers",)
