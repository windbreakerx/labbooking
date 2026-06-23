from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.bookings.views.health import HealthView
from apps.users.jwt_views import EmailTokenObtainPairView
from apps.users.views import SSOLoginView, WebLoginView, WebLogoutView
from config.views import favicon

urlpatterns = [
    path("favicon.ico", favicon, name="favicon"),
    path("admin/", admin.site.urls),
    path("login/", WebLoginView.as_view(), name="login"),
    path("logout/", WebLogoutView.as_view(), name="logout"),
    path("", include("apps.bookings.urls_web")),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/v1/auth/token/", EmailTokenObtainPairView.as_view(), name="token_obtain"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/sso/", SSOLoginView.as_view(), name="sso_login"),
    path("api/v1/", include("apps.bookings.urls_api")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
