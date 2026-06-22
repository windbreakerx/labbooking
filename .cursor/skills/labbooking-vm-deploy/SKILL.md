---
name: labbooking-vm-deploy
description: Handles safe labbooking deploy on Yandex VM with Docker, env, HTTPS, backup, cron, and smoke tests. Use when changing docker-compose, deploy scripts, production settings, SMTP, or VM troubleshooting docs.
---

# labbooking-vm-deploy

Use this skill when changing Docker, nginx, production settings, `.env.vm.example`, deploy scripts, backups, cron, SMTP, HTTPS, or VM troubleshooting docs.

## Pre-Deploy Checklist

- `DEBUG=0`, `DJANGO_SETTINGS_MODULE=config.settings.prod`.
- `SECRET_KEY`, database password, SMTP password are in `.env`, not in git.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` match the IP/domain.
- `SECURE_SSL_REDIRECT=0` only for first HTTP launch; enable it after HTTPS.
- `EMAIL_FAIL_SILENTLY=0` for pilot verification.

## Commands

```bash
bash scripts/deploy-vm.sh
bash scripts/smoke-test.sh http://127.0.0.1
bash scripts/backup_db.sh
docker compose -f docker-compose.yml -f docker-compose.vm.yml logs -f web
```

## Cron

```cron
0 * * * * cd ~/labbooking && docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T web python manage.py mark_visited
0 6 * * 1 cd ~/labbooking && docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T web python manage.py generate_sessions --weeks=4
```

## SMTP Check

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web \
  python manage.py shell -c "from django.core.mail import send_mail; send_mail('labbooking SMTP test', 'OK', None, ['your-email@example.com'], fail_silently=False)"
```
