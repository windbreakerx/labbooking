# labbooking-prod-security

Use this skill before production or pilot deploys, and when changing auth, permissions, staff routes, API endpoints, file uploads, environment variables, CORS/CSRF, rate limits, or email.

## Checklist

- Follow `.cursor/rules/security.md`.
- Staff/admin routes require login and role checks.
- JWT is for API; session auth is for web UI.
- CSRF remains enabled for web forms.
- CORS is restricted to known origins.
- Secrets stay in `.env` or VM secrets, never in git.
- PDF uploads stay limited by extension, size, and content checks where implemented.
- SMTP failures are observable in pilot/prod logs.
- `SSO_ENABLED=0` until OIDC/LDAP config is real.

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_student_scope.py apps/bookings/tests/test_staff_scope.py -v
```

If available in the environment:

```bash
bandit -r apps config
pip-audit
gitleaks detect --source ..
```

## Manual Security Matrix

- Student cannot access another group's discipline, lab work, booking, or support ticket.
- Staff cannot access another lab's bookings, sessions, support tickets, people, stands, schedule, or reports.
- Staff without a lab sees empty staff data.
- `SYS_ADMIN` bypass is intentional and tested.
