from django.contrib import admin

from .models import Department, Discipline, Faculty, LabWork, LabWorkMethodics, Semester, StudentGroup


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "ordering")
    ordering = ("ordering", "title")
    search_fields = ("code", "title")


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("title", "short_code", "faculty", "ordering")
    list_filter = ("faculty",)
    ordering = ("ordering", "title")


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty", "department", "dekanat_id")
    search_fields = ("name", "faculty", "dekanat_id")
    list_filter = ("faculty", "department")
    filter_horizontal = ("disciplines", "lab_works")


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "short_code", "department", "semester", "is_published")
    list_filter = ("semester", "department", "is_published", "training_centers")
    search_fields = ("title", "code", "short_code")
    filter_horizontal = ("training_centers", "laboratories")


@admin.register(LabWork)
class LabWorkAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "number", "duration_minutes", "capacity", "primary_stand", "is_published")
    list_filter = ("is_published", "training_centers", "disciplines")
    search_fields = ("title", "code")
    filter_horizontal = ("disciplines", "training_centers", "laboratories")


@admin.register(LabWorkMethodics)
class LabWorkMethodicsAdmin(admin.ModelAdmin):
    list_display = ("display_name", "lab_work", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("title", "lab_work__title")
