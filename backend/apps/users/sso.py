from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class SSOAuthError(Exception):
    pass


class SSOProvider:
    """OIDC/SAML/LDAP провайдер вуза. При SSO_ENABLED=0 — отключён."""

    def __init__(self):
        self.enabled = settings.SSO_ENABLED
        self.provider = getattr(settings, "SSO_PROVIDER", "")

    def authenticate(self, email: str, password: str) -> User | None:
        if not self.enabled:
            return None
        if self.provider == "oidc":
            return self._authenticate_oidc(email, password)
        raise NotImplementedError(
            "SSO integration is not configured. Set SSO_PROVIDER and endpoints in .env"
        )

    def _authenticate_oidc(self, email: str, password: str) -> User | None:
        if not all([
            settings.SSO_TOKEN_URL,
            settings.SSO_CLIENT_ID,
            settings.SSO_CLIENT_SECRET,
        ]):
            raise SSOAuthError("OIDC credentials not configured")
        raise NotImplementedError("OIDC token exchange — configure with university IdP")

    def get_authorization_url(self) -> str | None:
        if not self.enabled or not settings.SSO_AUTHORIZATION_URL:
            return None
        return settings.SSO_AUTHORIZATION_URL


def get_sso_provider() -> SSOProvider:
    return SSOProvider()
