# Развёртывание BKS Lab

Production-конфигурация находится в `docker-compose.yml`. Она отдельна
от локального `docker-compose.dev.yml`: БД и приложения не публикуют порты,
снаружи доступны только nginx 80/443. Backend и frontend работают от UID 1001.
Контент хранится в PostgreSQL и редактируется через админку; загруженные
изображения — в именованном volume `uploads` (раздаёт nginx). PostgreSQL,
uploads и сертификаты хранятся в именованных volumes. Не выполнять
`down -v` на рабочем сервере.

Первый серверный стенд разворачивается по IP, домен подключается после
его проверки. Конфигурация пока проверена только в отдельном локальном
HTTPS-окружении; серверная приёмка ещё не проведена.

Первый production-запуск выполняется с пустой БД: локальная БД, публикации
и uploads не переносятся. Все статьи, заметки и проекты создаются только
через редактор `/admin/content`. Markdown-файлы из `backend/content/`
не импортируются; они остаются историческим архивом.

## Перед первым запуском

Нужен Linux-сервер с Docker Engine и Compose v2, Git и Python 3. Первый
стенд проверяется на `91.218.114.82`, публичный DNS `bks-lab.ru` пока не
меняется. Первый стенд работает по HTTP на порту 80 без сертификата;
домен и HTTPS на порту 443 подключаются после проверки стенда.
Доступ к серверу предоставляет владелец.

```bash
python3 scripts/init-production-env.py
cp frontend/.env.production.example frontend/.env.production
chmod 600 backend/.env.production frontend/.env.production
```

Скрипт не перезаписывает существующий файл и не выводит секреты. Он создаёт
разные случайные пароли БД/админки и секреты статистики/публикации. В закрытом
редакторе заполнить `backend/.env.production`: `SITE_HOST` (hostname или IPv4 без схемы/порта).
Логин админки — `ADMIN_USERNAME`; пароль — `ADMIN_PASSWORD`.
В `frontend/.env.production` задать тот же `SITE_HOST`,
`SITE_URL=http://SITE_HOST` и тот же
`REVALIDATE_SECRET`, что у backend. Этот файл используется frontend и nginx;
backend и БД, как в референсах, получают `backend/.env.production`.
В backend-файле также согласовать `ADMIN_ALLOWED_ORIGINS` с `SITE_URL`.
Env-файлы не хранить в git и не прикладывать к отчётам.

Форма обращения сохраняет сообщение в PostgreSQL; владелец читает его в
`/admin/feedback` и при необходимости отвечает вручную. Дополнительное
подключение для обратной связи не требуется. Подписка сохраняет email;
автоматическая рассылка не входит в текущую реализацию.

`SITE_URL` и рекламные `NEXT_PUBLIC_*` из frontend-файла
используются при сборке через BuildKit secret. После их изменения выполнить
`docker compose --env-file backend/.env.production -f docker-compose.yml build --no-cache frontend`
и пересоздать frontend: содержимое secrets не меняет Docker build cache.
Приватный env-файл не сохраняется в образе. Изменение остальных
секретов требует пересоздания соответствующего контейнера. Для смены пароля
у уже созданной БД недостаточно поменять env: использовать PostgreSQL
`ALTER ROLE` и согласованно обновить конфигурацию приложения.

```bash
docker compose --env-file backend/.env.production -f docker-compose.yml config --quiet
docker compose --env-file backend/.env.production -f docker-compose.yml build
docker compose --env-file backend/.env.production -f docker-compose.yml up -d --wait db backend news-analyzer-scheduler frontend
```

Frontend собирается без живого API. Пустые списки допустимы только при
сборке; после запуска ошибки API обрабатываются как ошибки. Backend при
старте выполняет Alembic migrations, затем `python -m scripts.seed_news`;
перед обновлением существующего сервера создать резервную копию.

News Analyzer требует отдельного scheduler из того же backend-образа и
одинаковых `NEWS_*` у API и обработчика. Без параметров LLM собранные
материалы ожидают анализа. Seed заполняет каталог подсказок
(`news_source_catalogue`) из `backend/src/data/news_source_catalogue.json`,
а также темы и рубрики. В пустую БД добавляются все начальные записи;
при каждом следующем старте — только отсутствующие ID каталога и имена
тем/рубрик. Если новых записей нет, вставок и обновлений не выполняется;
в лог выводятся нулевые счётчики. Существующие записи, их порядок и
настройки подключённых источников не перезаписываются.

Каталог читается админкой из БД через защищённый
`GET /api/admin/news/sources/catalogue`. Seed не подключает источники и
не включает сбор: это делается через успешный предпросмотр в админке.
Таблицы публикаций остаются пустыми до создания материалов в редакторе.
Для отдельного повторного запуска seed можно выполнить:

```bash
docker compose --env-file backend/.env.production -f docker-compose.yml exec -T backend python -m scripts.seed_news
```

Конфигурация — в `.env.production.example`, подробности — в
[news_analyzer.md](news_analyzer.md).

## Первый стенд по IP: HTTP

По умолчанию Compose использует `infra/nginx/http`: nginx обслуживает сайт,
Admin API и загрузки на порту 80, без сертификата и перенаправления на HTTPS.

В `backend/.env.production` задать `SITE_HOST=91.218.114.82`,
`ADMIN_ALLOWED_ORIGINS=["http://91.218.114.82"]`, `ADMIN_COOKIE_SECURE=false`.
Во `frontend/.env.production` — тот же `SITE_HOST` и
`SITE_URL=http://91.218.114.82`. Если `NGINX_TEMPLATE_DIR` задан явно,
использовать `./infra/nginx/http`.

```bash
docker compose --env-file backend/.env.production -f docker-compose.yml up -d --build --wait
docker compose --env-file backend/.env.production -f docker-compose.yml exec -T nginx nginx -t
```

При изменении URL в существующем frontend env сначала пересобрать frontend
с `build --no-cache frontend`, затем пересоздать контейнеры. Проверять
`http://91.218.114.82`, включая вход в админку, редактор и каталог.

## Подключение домена и HTTPS после проверки IP

Настроить A-запись `bks-lab.ru` на `91.218.114.82`; после её обновления
выпустить доменный сертификат. Работающий nginx обслуживает ACME challenge
на порту 80:

```bash
docker compose --env-file backend/.env.production -f docker-compose.yml run --rm certbot certonly --webroot --webroot-path /var/www/certbot --domain bks-lab.ru --email YOUR_CERTIFICATE_EMAIL --agree-tos --no-eff-email
```

Заменить `YOUR_CERTIFICATE_EMAIL` адресом владельца сертификата.
Затем установить `SITE_HOST=bks-lab.ru` в обоих env-файлах,
`SITE_URL=https://bks-lab.ru` во frontend и
`ADMIN_ALLOWED_ORIGINS=["https://bks-lab.ru"]`, `ADMIN_COOKIE_SECURE=true`,
`NGINX_TEMPLATE_DIR=./infra/nginx/https` в backend. Пересобрать frontend без кеша
и пересоздать backend, чтобы применился новый разрешённый Origin:

```bash
docker compose --env-file backend/.env.production -f docker-compose.yml build --no-cache frontend
docker compose --env-file backend/.env.production -f docker-compose.yml up -d --build --wait backend news-analyzer-scheduler frontend
docker compose --env-file backend/.env.production -f docker-compose.yml up -d --force-recreate nginx
docker compose --env-file backend/.env.production -f docker-compose.yml exec -T nginx nginx -t
```

После подключения HTTPS добавить в cron на сервере запуск
`bash /absolute/path/bks-lab/scripts/renew-certificates.sh` дважды в сутки.
Скрипт проверяет срок сертификата через certbot, проверяет nginx и
перечитывает сертификат. Отслеживать ошибки cron.

При ошибке выпуска доменного сертификата сохранить рабочий HTTP-стенд по IP и
его `SITE_HOST`, исправить DNS/доступность challenge и повторить выпуск.
Не менять конфигурацию на домен до появления его сертификата.

## Проверка запуска

- `docker compose ... ps`: db/backend/news-analyzer-scheduler/frontend/nginx healthy.
- `http://91.218.114.82/api/health` на первом стенде: 200. После подключения
  домена — `https://bks-lab.ru/api/health`: 200, HTTP перенаправляет на HTTPS.
- Главная, пустые списки блога/заметок/проектов и `/sitemap.xml` открываются
  без ошибок и используют боевой домен. После создания материала в админке
  его страница и sitemap обновляются без пересборки frontend.
- `/admin` без входа открывает `/admin/login`; `/api/admin/overview` — 401
  с `Cache-Control: no-store`. После входа работают статистика и редактор:
  создание материала, загрузка изображения, сохранение и предпросмотр;
  после выхода прежняя сессия недействительна.
- Cookie `admin_session`: HttpOnly, SameSite=Strict, Path=/; Secure при HTTPS.
  Path нужен для серверной проверки страниц `/admin`; JS токен не читает.
- Обращение из формы появляется в `/admin/feedback` с именем, контактом для
  ответа, полным текстом и датой. Подписка появляется в разделе подписчиков.

Admin POST принимает только Origin из `ADMIN_ALLOWED_ORIGINS`, совпадающий
с `SITE_URL`: HTTP на первом стенде, HTTPS после подключения домена. Публичный вход —
nginx: он заменяет входящие `X-Real-IP` и `X-Forwarded-For` адресом посетителя.
Backend использует `X-Real-IP` для статистики и лимитов; его порт наружу
не публикуется. Сеть Docker — обычная `bridge` с автоматическими адресами;
контейнеры этой сети считаются доверенными.

Заголовки безопасности устанавливает nginx. CSP пока `Report-Only`:
проверить отчёты браузера с рабочими сценариями, затем перейти к enforced
CSP. У админки нет разрешений для рекламных доменов. Access log не включает
IP, User-Agent, referer, cookies или query-string; error log может содержать
диагностические данные. Docker-логи ротируются: до трёх файлов по 10 МБ на
контейнер. Срок хранения данных и окончательный текст политики должны
соответствовать решениям владельца и фактическому размещению.

## Публикация и обновления

Публикации создаются и редактируются в админке (`/admin/content`):
сохранение пишет версию в `content_revisions` и переводит материал в
статус `active`. После каждой мутации backend сам вызывает защищённый
webhook `POST /api/revalidate` фронтенда (секрет в заголовке
Authorization, не попадает в URL); страницы и sitemap обновляются без
пересборки. Если webhook недоступен, сохранение не падает — ISR-кэш
истечёт сам (5 минут). Отдельного скрипта публикации нет.

Обновление кода на сервере:

```bash
bash scripts/backup-database.sh
git pull --ff-only
docker compose --env-file backend/.env.production -f docker-compose.yml up -d --build --wait db backend news-analyzer-scheduler frontend
docker compose --env-file backend/.env.production -f docker-compose.yml up -d --force-recreate nginx
```

При откате сначала оценить совместимость миграций с прежним кодом. Не
делать автоматический downgrade или восстановление поверх рабочей БД.

## Резервное копирование

`bash scripts/backup-database.sh` создаёт приватный custom-format `pg_dump`
в `backups/`, проверяет читаемость `pg_restore --list` и только затем даёт
файлу окончательное имя; рядом сохраняется архив volume `uploads`
(изображения редактора). Настроить расписание, отдельное защищённое
хранилище и периодическое восстановление в тестовую БД. Копия на том же
диске не защищает от потери сервера. Контент теперь живёт только в БД и
uploads — эта резервная копия критична; секреты и сертификаты требуют
отдельной закрытой резервной копии.

## Реклама и ручная приёмка

Реклама выключена по умолчанию. После модерации площадки в Яндексе владелец
получает реальные ID и заполняет `NEXT_PUBLIC_YANDEX_AD_*_ID`, затем включает
`NEXT_PUBLIC_ADS_ENABLED=true` и пересобирает frontend. Проверить CLS,
контраст и CSP на реальных рекламных блоках. На главной и в админке рекламы нет.

До публичного запуска остаются ручные пункты дизайн-ТЗ §22: NVDA,
VoiceOver/TalkBack и нативный масштаб браузера, а также финальная оценка
владельцем контента, контактов и политики. Автоматические проверки их не
заменяют.
