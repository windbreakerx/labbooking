from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .forms import EmailAuthenticationForm
from .sso import SSOAuthError, get_sso_provider


class SSOLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        provider = get_sso_provider()
        if not provider.enabled:
            return Response(
                {"detail": "SSO отключён. Используйте /api/v1/auth/token/."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        email = request.data.get("email", "")
        password = request.data.get("password", "")
        try:
            user = provider.authenticate(email, password)
        except (SSOAuthError, NotImplementedError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_501_NOT_IMPLEMENTED)
        if user is None:
            return Response({"detail": "Неверные учётные данные."}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        return Response({"refresh": str(refresh), "access": str(refresh.access_token)})


class WebLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class WebLogoutView(LogoutView):
    next_page = "login"


@requires_csrf_token
def csrf_failure(request, reason=""):
    return render(
        request,
        "403_csrf.html",
        {"reason": reason},
        status=403,
    )
