# Security checklist — Lab Booking (lr.spmi.ru)

## Authentication & Authorization
- All admin and staff routes require authentication and role checks (`IsLabStaff`, `IsStudent`).
- Never expose Django admin or staff panels without login.
- JWT for API; session auth for web UI only.
- SSO adapter disabled by default (`SSO_ENABLED=0`); enable only with OIDC/LDAP config.

## Input validation
- All API input through DRF serializers only.
- Use Django ORM exclusively — no raw SQL with user input.
- Validate file uploads (PDF methodical guides) when added: size ≤ 10 MB, content-type check.

## Secrets
- `SECRET_KEY`, DB passwords, SMTP credentials only in `.env` / Docker secrets.
- Never commit `.env`; use `.env.example` as template.
- Run gitleaks / pre-commit secret scan before push.

## HTTP headers (nginx + Django)
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- HSTS enabled in production (`config.settings.prod`)

## CSRF & CORS
- CSRF enabled for session-based web forms.
- CORS restricted to known SPA origins via `CORS_ALLOWED_ORIGINS`.

## Rate limiting
- Apply rate limits on `/api/v1/auth/token/` and `/api/v1/bookings/` (django-ratelimit or nginx).

## Personal data (152-ФЗ)
- Store minimum PII: email, name, group.
- Audit log for booking changes (`AuditLog`).
- HTTPS mandatory in production.

## Dependencies
- CI runs `bandit` and `pip-audit` on every push.

## Reference
- Use Anthropic Cybersecurity Skills for OWASP Top 10 review before each release.
