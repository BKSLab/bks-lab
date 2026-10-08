# Развёртывание BKS Lab

Production-конфигурация находится в `docker-compose.prod.yml`. Она отдельна
от локального `docker-compose.yml`: БД и приложения не публикуют порты,
снаружи доступны только nginx 80/443. Backend и frontend работают от UID 1001.
Контент подключается read-only из `backend/content`; PostgreSQL и сертификаты
хранятся в именованных volumes. Не выполнять `down -v` на рабочем сервере.

Публичный запуск отложен владельцем. Эта инструкция описывает последующий
деплой; пока конфигурация проверена только в отдельном локальном HTTPS-окружении.

## Перед первым запуском

Нужен Linux-сервер с Docker Engine и Compose v2, Git и Python 3. DNS-запись
`bks-lab.ru` должна указывать на него; порты 80/443 должны быть доступны.
Доступ к серверу и почтовый аккаунт предоставляет владелец.

```bash
python3 scripts/init-production-env.py
chmod 600 .env.production
```

Скрипт не перезаписывает существующий файл и не выводит секреты. Он создаёт
разные случайные пароли БД/админки и секреты статистики/публикации. В закрытом
редакторе заполнить `.env.production`: `SITE_HOST` (только hostname),
`CONTACT_EMAIL`, `SMTP_HOST`, порт, логин/пароль, `SMTP_SENDER`,
`SMTP_RECIPIENT`. Логин админки — `ADMIN_USERNAME`; пароль — `ADMIN_PASSWORD`.
Файл не хранить в git и не прикладывать к отчётам.

Для порта 587 обычно нужны `SMTP_START_TLS=true`, `SMTP_USE_TLS=false`;
для implicit TLS на 465 — наоборот. Сверить с настройками своего провайдера.
Без SMTP сайт работает, но форма обращения честно отвечает недоступностью
почты и не сообщает об успешной отправке. Подписка сохраняет email;
автоматическая рассылка не входит в текущую реализацию.

`SITE_HOST`, `CONTACT_EMAIL`, рекламные `NEXT_PUBLIC_*` используются во
время сборки: после их изменения пересобрать frontend. Изменение остальных
секретов требует пересоздания соответствующего контейнера. Для смены пароля
у уже созданной БД недостаточно поменять env: использовать PostgreSQL
`ALTER ROLE` и согласованно обновить конфигурацию приложения.

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --wait db backend news-analyzer-scheduler frontend
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python -m scripts.seed_news
```

Frontend собирается без живого API. Пустые списки допустимы только при
сборке; после запуска ошибки API обрабатываются как ошибки. Backend при
старте выполняет Alembic migrations; перед обновлением существующего
сервера создать резервную копию.

News Analyzer требует отдельного scheduler из того же backend-образа и
одинаковых `NEWS_*` у API и обработчика. Без параметров LLM собранные
материалы ожидают анализа. Seed добавляет только темы/рубрики; источники
подключаются через предпросмотр в админке. Конфигурация — в
`.env.production.example`, подробности — в [news_analyzer.md](news_analyzer.md).

## HTTPS

Сначала запустить единственный nginx в режиме выдачи ACME challenge.
В этом режиме приложение по HTTP не отдаётся.

```bash
NGINX_TEMPLATE_DIR=./infra/nginx/http docker compose --env-file .env.production -f docker-compose.prod.yml up -d nginx
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm certbot certonly --webroot --webroot-path /var/www/certbot --domain bks-lab.ru --email YOUR_CERTIFICATE_EMAIL --agree-tos --no-eff-email
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --force-recreate nginx
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T nginx nginx -t
bash scripts/publish-content.sh
```

В команде certbot заменить домен на `SITE_HOST` и email на настоящий адрес
владельца сертификата. Выпуск сертификата — внешний шаг после настройки DNS.
При ошибке certbot оставить bootstrap-режим, исправить DNS/доступность
challenge и повторить только выпуск. Не переключать nginx на HTTPS до
появления сертификата.

Добавить в cron на сервере запуск `bash /absolute/path/bks-lab/scripts/renew-certificates.sh`
дважды в сутки. Скрипт проверяет срок сертификата через certbot, проверяет
nginx и перечитывает сертификат. Отслеживать ошибки cron. Отдельный Docker
socket в контейнеры не передаётся.

## Проверка запуска

- `docker compose ... ps`: db/backend/news-analyzer-scheduler/frontend/nginx healthy.
- `https://bks-lab.ru/api/health`: 200; HTTP перенаправляет на HTTPS.
- Главная, статья, проект, `/sitemap.xml` используют боевой домен и контент.
- `/admin` без входа открывает `/admin/login`; `/api/admin/overview` — 401
  с `Cache-Control: no-store`. После входа работают статистика и материалы;
  после выхода прежняя сессия недействительна.
- Cookie `admin_session`: HttpOnly, Secure, SameSite=Strict, Path=/.
  Path нужен для серверной проверки страниц `/admin`; JS токен не читает.
- Сообщение формы приходит в настроенный ящик, подписка появляется в админке.
  Проверка доставки на настоящую почту выполняется владельцем перед запуском.

Admin POST принимает только Origin `https://SITE_HOST`. Backend доверяет
IP-заголовкам только от фиксированного IP nginx; входящая пользовательская
цепочка X-Forwarded-For заменяется. Если заданная Docker-подсеть конфликтует
с сетью сервера, поменять `BKS_NETWORK_SUBNET` и `BKS_PROXY_IP` вместе.

Заголовки безопасности устанавливает nginx. CSP пока `Report-Only`:
проверить отчёты браузера с рабочими сценариями, затем перейти к enforced
CSP. У админки нет разрешений для рекламных доменов. Access log не включает
IP, User-Agent, referer, cookies или query-string; error log может содержать
диагностические данные. Docker-логи ротируются: до трёх файлов по 10 МБ на
контейнер. Срок хранения данных и окончательный текст политики должны
соответствовать решениям владельца и фактическому размещению.

## Публикация и обновления

После получения Markdown-файлов в `backend/content`:

```bash
bash scripts/publish-content.sh
# При чистом рабочем дереве можно сначала получить текущую upstream-ветку:
bash scripts/publish-content.sh --pull
```

Скрипт ждёт TTL файлового кэша, проверяет доступность трёх типов контента,
вызывает защищённый webhook и прогревает основные страницы/sitemap.
Секрет берётся внутри frontend-контейнера из env, передаётся в заголовке
Authorization и не попадает в URL или командную строку. Новые статьи
рендерятся по запросу без пересборки. Для изменения кода нужен обычный
build/up; `publish-content.sh` не заменяет обновление контейнеров.

```bash
bash scripts/backup-database.sh
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build --wait db backend frontend
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --force-recreate nginx
bash scripts/publish-content.sh
```

При откате сначала оценить совместимость миграций с прежним кодом. Не
делать автоматический downgrade или восстановление поверх рабочей БД.

## Резервное копирование

`bash scripts/backup-database.sh` создаёт приватный custom-format `pg_dump`
в `backups/`, проверяет читаемость `pg_restore --list` и только затем даёт
файлу окончательное имя. Настроить расписание, отдельное защищённое хранилище
и периодическое восстановление в тестовую БД. Копия на том же диске не
защищает от потери сервера. Markdown и изображения сохраняются в git;
секреты и сертификаты требуют отдельной закрытой резервной копии.

## Реклама и ручная приёмка

Реклама выключена по умолчанию. После модерации площадки в Яндексе владелец
получает реальные ID и заполняет `NEXT_PUBLIC_YANDEX_AD_*_ID`, затем включает
`NEXT_PUBLIC_ADS_ENABLED=true` и пересобирает frontend. Проверить CLS,
контраст и CSP на реальных рекламных блоках. На главной и в админке рекламы нет.

До публичного запуска остаются ручные пункты дизайн-ТЗ §22: NVDA,
VoiceOver/TalkBack и нативный масштаб браузера, а также финальная оценка
владельцем контента, контактов и политики. Автоматические проверки их не
заменяют.
