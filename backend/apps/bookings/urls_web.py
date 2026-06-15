from django.urls import path

from apps.bookings.views.web import (
    BookLabWorkWebView,
    CancelBookingWebView,
    DisciplineListWebView,
    HomeView,
    LabWorkListWebView,
    MyBookingsWebView,
    StaffBookingsWebView,
    StaffStatusUpdateWebView,
    SupportCreateWebView,
    SupportListWebView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("disciplines/", DisciplineListWebView.as_view(), name="disciplines"),
    path(
        "disciplines/<int:discipline_id>/lab-works/",
        LabWorkListWebView.as_view(),
        name="lab-works",
    ),
    path("lab-works/<int:lab_work_id>/book/", BookLabWorkWebView.as_view(), name="book-lab-work"),
    path("my-bookings/", MyBookingsWebView.as_view(), name="my-bookings"),
    path("my-bookings/<int:pk>/cancel/", CancelBookingWebView.as_view(), name="cancel-booking"),
    path("support/", SupportListWebView.as_view(), name="support"),
    path("support/create/", SupportCreateWebView.as_view(), name="support-create"),
    path("staff/bookings/", StaffBookingsWebView.as_view(), name="staff-bookings"),
    path(
        "staff/bookings/<int:pk>/status/",
        StaffStatusUpdateWebView.as_view(),
        name="staff-booking-status",
    ),
]
