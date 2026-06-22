---
name: anthropic-cybersecurity
description: Routes labbooking security reviews to the Anthropic Cybersecurity Skills library in the repo vendor submodule. Use for OWASP-style reviews, access control testing, JWT/API security, XSS, secrets, and pre-release security hardening beyond labbooking-prod-security.
---

# anthropic-cybersecurity

Use this skill together with `labbooking-prod-security` when you need deeper security guidance than the project checklist.

## Library Location

The full library lives in the repo submodule:

`.cursor/skills/vendor/Anthropic-Cybersecurity-Skills/skills/`

After `git pull` on a new machine, initialize it once:

```bash
git submodule update --init --recursive
```

## Labbooking-Relevant Skills

Prefer these skills for this Django/DRF/HTMX project:

| Skill folder | When to use |
|--------------|-------------|
| `testing-for-broken-access-control` | Staff/student/lab scoping, IDOR, role checks |
| `testing-api-security-with-owasp-top-10` | DRF endpoints, auth, input validation |
| `testing-for-xss-vulnerabilities` | HTMX templates, user-generated text |
| `testing-jwt-token-security` | SimpleJWT settings and token flows |
| `testing-cors-misconfiguration` | API CORS before SPA or external clients |
| `testing-for-sensitive-data-exposure` | PII, secrets, `.env`, reports |
| `analyzing-web-server-logs-for-intrusion` | nginx/gunicorn logs on VM |

Read the matching `SKILL.md` from the vendor path before applying its workflow.

## Workflow

1. Start with `labbooking-prod-security` and `.cursor/rules/security.md`.
2. Pick one vendor skill that matches the task.
3. Apply its checklist to the changed files only.
4. Run project tests:

```bash
cd backend
pytest apps/bookings/tests/test_student_scope.py apps/bookings/tests/test_staff_scope.py -v
```

## Do Not Use For

- Routine Django feature work unrelated to security.
- Replacing `BookingService` business rules.
- Full malware forensics or cloud IR unless explicitly requested.
