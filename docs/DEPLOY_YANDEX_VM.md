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
```

С телефона или домашнего ПК:
- http://\<PUBLIC_IP\>/
- http://\<PUBLIC_IP\>/api/docs/

**Вход:** `student@stud.spmi.ru` / `student123`

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
```

## Остановка / перезапуск

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml down
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d
```

## Устранение неполадок

| Симптом | Решение |
|---------|---------|
| `DisallowedHost` | Добавьте IP в `ALLOWED_HOSTS` в `.env`, перезапустите web |
| 502 от nginx | `docker compose ... logs web` — ждите migrate |
| Нет стилей | `docker compose ... exec web python manage.py collectstatic --noinput` |
| Не открывается снаружи | Проверьте Security Group (порт 80) и `ufw` на VM: `sudo ufw allow 80` |
| Забыли пароль БД | Совпадают `POSTGRES_PASSWORD` и пароль в `DATABASE_URL` |

Логи:
```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml logs -f web
```

## HTTPS (домен)

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
```

## Схема на VM

```
Интернет :80 → nginx → gunicorn (web) → PostgreSQL (db)
                              ↘ Redis (cache)
```

Файлы overlay: `docker-compose.yml` + `docker-compose.vm.yml`
