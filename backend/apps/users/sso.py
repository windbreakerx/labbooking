from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class SSOAuthError(Exception):
    pass


class SSOProvider:
    """Абстракция для будущей интеграции с вузовским OIDC/SAML/LDAP."""

    def __init__(self):
        self.enabled = settings.SSO_ENABLED

    def authenticate(self, email: str, password: str) -> User | None:
        if not self.enabled:
            return None
        raise NotImplementedError("SSO integration is not configured yet")

    def get_authorization_url(self) -> str | None:
        if not self.enabled:
            return None
        return None


def get_sso_provider() -> SSOProvider:
    return SSOProvider()
