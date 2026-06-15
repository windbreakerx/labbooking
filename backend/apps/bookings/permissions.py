from rest_framework import permissions

from apps.bookings.services import is_staff_user
from apps.users.models import UserRole


class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.STUDENT


class IsLabStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and is_staff_user(request.user)
