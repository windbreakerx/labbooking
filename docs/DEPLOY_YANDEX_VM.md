# Деплой на Yandex Cloud VM (вечер, ~30–45 мин)

Пошаговая инструкция: поднять **labbooking** в Docker на Ubuntu VM и открыть сайт по публичному IP.

## Что понадобится

- VM в Yandex Cloud (Ubuntu 22.04/24.04, 2 vCPU / 4 GB)
- Публичный IP
- Security Group: входящие **22** (SSH), **80** (HTTP), **443** (HTTPS, при домене)
- Доступ **дома** (SSH с работы может быть заблокирован)

## Часть A — на работе (без SSH к VM)

1. Закоммитьте и запушьте код:
   ```bash
   cd labbooking
   git add .
   git commit -m "Prepare VM deploy"
   git push
   ```
2. Запишите **публичный IP** VM из консоли Yandex Cloud.
3. Сгенерируйте `SECRET_KEY` (можно дома):  
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`

## Часть B — дома на VM (SSH)

### 1. Подключение

```bash
ssh ubuntu@<PUBLIC_IP>
# или: ssh -i ~/.ssh/yandex_key ubuntu@<PUBLIC_IP>
```

### 2. Установка Docker (один раз)

```bash
sudo apt update
sudo apt install -y git ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

### 3. Клонирование проекта

```bash
git clone https://github.com/<you>/labbooking.git
cd labbooking
```

Или с флешки / `scp -r labbooking ubuntu@<IP>:~/`

### 4. Настройка `.env`

```bash
cp .env.vm.example .env
nano .env
```

Обязательно измените:

```env
SECRET_KEY=<длинная-случайная-строка>
ALLOWED_HOSTS=<DOMAIN>,<PUBLIC_IP>
POSTGRES_PASSWORD=<сильный-пароль>
DATABASE_URL=postgres://labbooking:<тот-же-пароль>@db:5432/labbooking
DEBUG=0
DJANGO_SETTINGS_MODULE=config.settings.prod
SECURE_SSL_REDIRECT=0
EMAIL_FAIL_SILENTLY=0
```

Для первого запуска без домена оставьте `SECURE_SSL_REDIRECT=0` и `USE_HTTPS=0`. После выпуска сертификата включите `USE_HTTPS=1` и `SECURE_SSL_REDIRECT=1`.

Для пилота переключите email на SMTP и проверьте доставку до открытия студентам:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.university.ru
EMAIL_PORT=587
EMAIL_HOST_USER=labbooking@university.ru
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_USE_TLS=1
DEFAULT_FROM_EMAIL=labbooking@university.ru
EMAIL_FAIL_SILENTLY=0
```

### 5. Запуск

```bash
bash scripts/deploy-vm.sh
```

Или вручную:

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py seed_demo
```

### 6. Проверка

С VM:
```bash
curl http://127.0.0.1/api/health/
bash scripts/smoke-test.sh http://127.0.0.1
```

С телефона или домашнего ПК:
- http://\<PUBLIC_IP\>/
- http://\<PUBLIC_IP\>/api/docs/

**Вход:** `student@stud.spmi.ru` / `student123`

Проверка SMTP из контейнера:

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web \
  python manage.py shell -c "from django.core.mail import send_mail; send_mail('labbooking SMTP test', 'OK', None, ['your-email@example.com'], fail_silently=False)"
```

### 7. Админ (опционально)

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py createsuperuser
```

Админка: http://\<PUBLIC_IP\>/admin/

## Обновление после правок кода

На VM:
```bash
cd ~/labbooking
git pull
bash scripts/deploy-vm.sh
bash scripts/smoke-test.sh http://127.0.0.1
```

`deploy-vm.sh` автоматически подключает `docker-compose.https.yml`, если:
- в `nginx/ssl/` есть `fullchain.pem` и `privkey.pem`, **или**
- в `.env` указано `USE_HTTPS=1`.

Рекомендуется после настройки HTTPS добавить в `.env`:
```env
USE_HTTPS=1
SITE_URL=https://spmi-lab.ru
SECURE_SSL_REDIRECT=1
```

## Остановка / перезапуск

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml down
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d
```

## Backup PostgreSQL

Перед обновлениями и перед живым пилотом сделайте дамп БД:

```bash
bash scripts/backup_db.sh
```

Скрипт сохраняет файл в `backups/`. Для rehearsal restore на отдельной тестовой базе:

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T db createdb -U labbooking labbooking_restore_check
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T db psql -U labbooking -d labbooking_restore_check < backups/<backup-file>.sql
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T db dropdb -U labbooking labbooking_restore_check
```

Не храните дампы с персональными данными в git или публичных хранилищах.

## Устранение неполадок

| Симптом | Решение |
|---------|---------|
| `DisallowedHost` | Добавьте IP в `ALLOWED_HOSTS` в `.env`, перезапустите web |
| `auth.docker.io` / `failed to fetch anonymous token` | Docker Hub недоступен с VM. Обновите код (`git pull`) — образ берётся из `public.ecr.aws`. Или настройте mirror (см. ниже) |
| 502 от nginx | `docker compose ... logs web` — ждите migrate |
| Нет стилей | `docker compose ... exec web python manage.py collectstatic --noinput` |
| Не открывается снаружи | Проверьте Security Group (порт 80) и `ufw` на VM: `sudo ufw allow 80` |
| Забыли пароль БД | Совпадают `POSTGRES_PASSWORD` и пароль в `DATABASE_URL` |

Логи:
```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml logs -f web
```

### Docker Hub недоступен (`auth.docker.io: 404`)

С VM в РФ `docker.io` часто не отвечает. В проекте базовый образ Python берётся из зеркала AWS ECR Public (`public.ecr.aws/docker/library/python`).

После `git pull` пересоберите:

```bash
bash scripts/deploy-vm.sh
```

Если ошибка остаётся, проверьте доступ к ECR:

```bash
docker pull public.ecr.aws/docker/library/python:3.12-slim
```

Запасной вариант — mirror для Docker Hub в `/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": ["https://mirror.gcr.io"]
}
```

Затем: `sudo systemctl restart docker`

## HTTPS (домен)

### Вариант A — сертификат уже выпущен в Yandex Certificate Manager (Issued)

1. A-запись домена → IP VM, порт **443** в Security Group.
2. На VM установите [yc CLI](https://yandex.cloud/ru/docs/cli/quickstart) и выполните `yc init`.
3. Скачайте сертификат и включите HTTPS:
   ```bash
   bash scripts/setup-https-ycm.sh spmi-lab.ru --name cert-spmi-lab
   # или по ID: bash scripts/setup-https-ycm.sh spmi-lab.ru fpqxxxxxxxx
   ```
4. В `.env`:
   ```env
   ALLOWED_HOSTS=spmi-lab.ru,www.spmi-lab.ru,<PUBLIC_IP>,localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=https://spmi-lab.ru,https://www.spmi-lab.ru
   SECURE_SSL_REDIRECT=1
   ```
5. Перезапуск: `docker compose -f docker-compose.yml -f docker-compose.vm.yml -f docker-compose.https.yml up -d`

### Вариант B — certbot на VM (без Certificate Manager)

1. A-запись домена → IP VM
2. На VM:
   ```bash
   sudo bash scripts/setup-https.sh your.domain.ru
   ```
3. В `.env`:
   ```env
   ALLOWED_HOSTS=your.domain.ru,<PUBLIC_IP>
   CSRF_TRUSTED_ORIGINS=https://your.domain.ru
   SECURE_SSL_REDIRECT=1
   ```
4. Перезапуск: `bash scripts/deploy-vm.sh`

## Smoke test

```bash
bash scripts/smoke-test.sh http://127.0.0.1
# или с доменом:
bash scripts/smoke-test.sh https://your.domain.ru
```

## Pytest на VM

Production-образ не содержит `pytest`. Для pilot gate используйте:

```bash
bash scripts/run-tests-vm.sh
bash scripts/run-tests-vm.sh apps/bookings/tests/test_staff_scope.py -v
bash scripts/run-tests-vm.sh --full
```

Скрипт ставит `requirements-dev.txt` в контейнер и запускает `python -m pytest`.
После `deploy-vm.sh --build` dev-зависимости нужно установить снова (скрипт делает это автоматически).

## Cron на VM (опционально)

```bash
# Авто VISITED после окончания слотов — каждый час
0 * * * * cd ~/labbooking && docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T web python manage.py mark_visited

# Генерация слотов из расписания — по понедельникам
0 6 * * 1 cd ~/labbooking && docker compose -f docker-compose.yml -f docker-compose.vm.yml exec -T web python manage.py generate_sessions --weeks=4
```

## Импорт из Деканата (CSV, до API)

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /path/students.csv --type=students
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /path/staff.csv --type=staff
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /path/teachers.csv --type=teachers
docker compose -f docker-compose.yml -f docker-compose.vm.yml exec web python manage.py import_dekanat_csv /path/disciplines.csv --type=disciplines --semester "Пилот 2026/2027 (нефтегаз)"
```

Шаблоны CSV для пилота: `docs/csv_templates/`, сценарий наполнения: `docs/PILOT_DATA_SETUP.md`.

## Схема на VM

```
Интернет :80 → nginx → gunicorn (web) → PostgreSQL (db)
                              ↘ Redis (cache)
```

Файлы overlay: `docker-compose.yml` + `docker-compose.vm.yml`
