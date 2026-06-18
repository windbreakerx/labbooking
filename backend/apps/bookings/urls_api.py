from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.bookings.views.api import (
    AdminBookingListView,
    AdminReportView,
    BookingCancelView,
    BookingCreateView,
    BookingStatusUpdateView,
    DisciplineLabWorksView,
    DisciplineListView,
    LabSessionAdminViewSet,
    LabSessionDetailView,
    LabSessionFilterView,
    LabSessionListView,
    ManualBookingView,
    MyBookingsView,
    SupportMessageView,
    SupportTicketViewSet,
    WaitlistJoinView,
)

router = DefaultRouter()
router.register(r"support/tickets", SupportTicketViewSet, basename="support-ticket")
router.register(r"admin/sessions", LabSessionAdminViewSet, basename="admin-session")

urlpatterns = [
    path("disciplines/", DisciplineListView.as_view(), name="discipline-list"),
    path("disciplines/<int:pk>/lab-works/", DisciplineLabWorksView.as_view(), name="discipline-lab-works"),
    path("sessions/", LabSessionListView.as_view(), name="session-list"),
    path("sessions/filters/", LabSessionFilterView.as_view(), name="session-filters"),
    path("sessions/<int:pk>/", LabSessionDetailView.as_view(), name="session-detail"),
    path("bookings/", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("me/bookings/", MyBookingsView.as_view(), name="api-my-bookings"),
    path("waitlist/", WaitlistJoinView.as_view(), name="api-waitlist-join"),
    path(
        "support/tickets/<int:ticket_id>/messages/",
        SupportMessageView.as_view(),
        name="support-message",
    ),
    path("admin/bookings/", AdminBookingListView.as_view(), name="admin-bookings"),
    path("admin/bookings/<int:pk>/status/", BookingStatusUpdateView.as_view(), name="booking-status"),
    path("admin/bookings/manual/", ManualBookingView.as_view(), name="booking-manual"),
    path("admin/reports/<str:report_type>/", AdminReportView.as_view(), name="admin-report"),
    path("", include(router.urls)),
]
