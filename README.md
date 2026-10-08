# BKS Lab

Личный сайт-портфолио и блог (bks-lab.ru): статьи, заметки, проекты,
статистика посещений, админка и редакционный News Analyzer для владельца.

## Возможности и состояние

- Главная, блог с поиском и рубриками, заметки, проекты, страницы об авторе
  и контакты. Светлая базовая тема, тёмная тема, фирменные изображения и
  вывеска BKS Lab в оформлении страницы.
- Подписка, форма обратной связи через SMTP, статистика посещений,
  metadata/Open Graph и sitemap. Рекламные места подготовлены, РСЯ выключена.
- Закрытая панель `/admin`: обзор, статистика, реестр публикаций и подписчики.
- Редакционный центр `/admin/news`: RSS/Atom и HTML-источники с предпросмотром,
  фоновый сбор, анализ внешней LLM, подборки для статей и коротких новостей,
  решения редактора, история и настройки.

**На 08.10.2026 согласованная функциональность реализована и проверена
локально, включая отдельный production-стенд с HTTPS.** Публичное
развёртывание на bks-lab.ru, рабочая почта/контакты, активация РСЯ и полная
ручная приёмка доступности отложены владельцем. Автоматические проверки
не означают, что эти пункты выполнены. Sentry, CMS, SearXNG и генерация
публикаций остаются за пределами текущего MVP.

## Стек

- **Backend:** Python 3.12, FastAPI, Hypercorn, Pydantic v2 + pydantic-settings,
  SQLAlchemy 2 (async) + asyncpg, Alembic, PostgreSQL 16.
- **Frontend:** Next.js 16 (App Router) + React 19 + TypeScript, Tailwind CSS 4.
- **News Analyzer:** RSS/Atom и HTML, внешняя LLM, очередь в PostgreSQL,
  APScheduler в отдельном процессе `news-analyzer-scheduler`.
- **Инфраструктура:** Docker + Compose (dev: `db`, `backend`,
  `news-analyzer-scheduler`; prod дополнительно frontend, nginx с TLS,
  certbot). Новых открытых портов для News Analyzer нет.

Документация: `docs/architecture.md`, `docs/api_contract.md`,
`docs/content_format.md`, `docs/implementation_plan.md`, дизайн-ТЗ —
`BKS_Lab_frontend_design_spec.md`. Запуск на сервере, публикация контента,
резервные копии и сертификаты: [docs/deployment.md](docs/deployment.md).
Редакционный центр и фоновый сбор: [docs/news_analyzer.md](docs/news_analyzer.md).

## Структура репозитория

```text
backend/    FastAPI-приложение: main.py, src/ (api, services, repositories,
            db, dependencies, schemas, core, ...), content/ (Markdown),
            scripts/, tests/, Dockerfile
frontend/   Next.js: публичная часть, админка, дизайн-токены, public/ с ассетами
docs/       архитектура, контракт API, формат контента, план реализации
search_news/  ТЗ News Analyzer и исследовательский каталог источников
референсы/  исходные визуальные материалы
docker-compose.yml  dev: db (PostgreSQL 16), backend, news-analyzer-scheduler
docker-compose.prod.yml  production-окружение с HTTPS
infra/nginx/  шаблоны nginx для выпуска сертификата и HTTPS
scripts/     конфигурация prod, публикация контента, backup, обновление TLS
```

## Быстрый старт (dev)

Требования: Docker, Python 3.12, Node.js 22.22.2+ (ветка 22) или 24.15+
(ветка 24). Эти версии поддерживают серверную санитизацию HTML публикаций.

1. Подготовить конфигурацию бэкенда:

   ```bash
   cp backend/.env.example backend/.env   # затем заполнить значения
   ```

2. Поднять БД, бэкенд и фоновый обработчик в Docker:

   ```bash
   docker compose up -d --build db backend news-analyzer-scheduler
   curl http://localhost:8000/api/health   # {"status":"ok"}
   ```

   PostgreSQL доступен с хоста на порту 5434 (для IDE). Код бэкенда
   смонтирован в контейнер: HTTP-сервер подхватывает правки через `--reload`.
   После изменения кода фонового обработчика перезапустите
   `docker compose restart news-analyzer-scheduler`; после изменения env
   пересоздайте контейнеры.

   Локальный запуск бэкенда без Docker (против Docker-БД):

   ```bash
   cd backend
   pip install -r requirements-dev.txt
   hypercorn main:app --reload --bind 127.0.0.1:8000   # POSTGRES_HOST=localhost POSTGRES_PORT=5434
   ```

3. Запустить фронтенд локально:

   ```bash
   cd frontend
   cp .env.example .env.local   # при необходимости
   npm ci
   npm run dev                  # http://localhost:3000
   ```

   В dev `next.config.ts` проксирует `/api/v1/*`, `/api/admin/*` и
   `/api/health` на backend. `/api/revalidate` обрабатывает сам Next.js.

Начальная конфигурация не содержит учётных данных администратора, SMTP
и LLM. Заполните нужные значения в локальном env; копии `.env.example`
сами по себе эти подключения не включают. Формы, модель и реклама
настраиваются независимо.

Для локальной админки задать в `backend/.env` собственные `ADMIN_USERNAME`
и `ADMIN_PASSWORD`, `ADMIN_ALLOWED_ORIGINS=["http://localhost:3000"]`,
`ADMIN_COOKIE_SECURE=false`, затем пересоздать backend командой
`docker compose up -d --force-recreate backend`. Если открываете сайт через
`127.0.0.1`, добавить этот origin в массив. Войти на `/admin/login`.
В production cookie всегда Secure; не переносить локальное значение `false`.
Админка показывает статистику, материалы и подписчиков; публикации меняются
только в Markdown. Редакционный центр `/admin/news` отдельно управляет
источниками, анализом и решениями по найденным материалам. Пустые учётные
данные отключают вход.

Для формы обратной связи настроить `SMTP_*` из `backend/.env.example`.
Без почты форма сообщает о недоступности отправки. Подписка сохраняется
в PostgreSQL; автоматическая рассылка не включена. Публичный адрес автора
задаётся через `CONTACT_EMAIL` в `frontend/.env.local` до сборки.

При прямом подключении к backend `APP_TRUSTED_PROXIES` остаётся пустым
(`[]`): присланные клиентом IP-заголовки игнорируются. За nginx задайте в
`backend/.env` JSON-массив его реальных IP/CIDR. Не разрешайте все адреса
или общую сеть с недоверенными контейнерами. В dev без доверенного прокси
статистика и лимит запросов используют адрес непосредственного соединения.

## News Analyzer

После запуска backend миграции применяются автоматически, затем стартует
`news-analyzer-scheduler`. Он использует тот же образ и PostgreSQL, работает
без открытой админки и не публикует HTTP-порт. Для начального заполнения тем
и рубрик:

```bash
docker compose exec backend python -m scripts.seed_news
```

При локальном backend выполните `python -m scripts.seed_news` из каталога
`backend`. Команда добавляет недостающие записи справочников; источники
не создаёт и сбор для них не включает.

При работе без backend-контейнеров запустите из `backend` также отдельный
процесс `python -m src.background_tasks.news_scheduler` с той же env-
конфигурацией PostgreSQL. Одного HTTP-сервера недостаточно для обработки
фоновой очереди.

Параметры модели задаются только в игнорируемом `backend/.env`:
`NEWS_LLM_PROVIDER`, `NEWS_LLM_API_URL`, `NEWS_LLM_API_KEY` и `NEWS_LLM_MODEL`.
Используется минимально адаптированный клиент из референса
`vera_rag_service/LLM_CLIENT_REFERENCE.md`. Текущая локальная конфигурация —
Polza; модель меняется одной строкой:

```dotenv
NEWS_LLM_MODEL=qwen/qwen3-30b-a3b-instruct-2507
```

После изменения env пересоздайте оба процесса:

```bash
docker compose up -d --force-recreate backend news-analyzer-scheduler
```

Ключ не передаётся фронтенду; в настройках видны только наличие конфигурации,
провайдер и модель. Без настроенной LLM материалы сохраняются в ожидании
анализа. Учёт расходов и денежные лимиты не реализованы.

Рабочий сценарий:

1. В `/admin/news/sources/new` укажите URL или подставьте адрес из каталога,
   нажмите «Проверить источник» и дождитесь предпросмотра. Для HTML можно
   настроить CSS-селекторы и повторить проверку.
2. Выберите темы, рубрики и нужную частоту; включите регулярный сбор и
   сохраните источник. Новый или изменённый URL нельзя сохранить без
   успешной проверки. Каталог сам ничего не подключает.
3. Запустите ручной сбор в «Запусках» или дождитесь расписания. По умолчанию
   это `08:00`, `14:00`, `20:00` в `Europe/Samara`; начальный интервал
   источника — 6 часов. Расписание, политика, веса и сроки хранения
   изменяются в `/admin/news/settings`.
4. В подборках «Для статей» и «Короткие новости» просмотрите оценки и
   первоисточник, затем выберите «В работу», «Отложить» или «Отклонить».
   Ожидающие анализа материалы доступны во вкладке «Все материалы».

Аннотация ограничена 500 символами, комментарий модели — 600. Редактор
проверяет первоисточник и принимает решение самостоятельно. «Повторить
анализ» обновляет результат для текущей модели и политики; простая смена
настроек не пересчитывает уже разобранный архив. Правила истории,
восстановления заданий и хранения описаны в [инструкции News Analyzer](docs/news_analyzer.md).

Ручной сбор, проверка источника и повторный анализ возвращают задание сразу;
его состояние доступно по ссылке `/admin/news/jobs/{id}`. По умолчанию первый
обход ограничен 30 днями и 50 материалами на источник, фрагмент для модели —
3000 символами, пакет анализа — 20 материалами. Настройки ограничивают объём
работы, сохраняя собранные материалы при сбое модели. Автопубликации и
изменения Markdown из редакционного центра нет.

В production используйте `NEWS_*` из `.env.production.example` и команды
Compose из [инструкции развёртывания](docs/deployment.md). Оба процесса
должны получать одну конфигурацию LLM; секреты не коммитятся.

## Тесты и проверки

Каждый блок запускается из корня репозитория. Для backend используйте
отдельное Python-окружение. Пример для PowerShell:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m pytest backend/tests
```

На Linux/macOS путь к интерпретатору — `backend/.venv/bin/python`.
Frontend:

```bash
cd frontend
npm ci
npm run lint
npx tsc --noEmit
npx vitest run
npm run build -- --webpack
npm audit --omit=dev
```

Backend-тестам нужен работающий Docker: `testcontainers` запускает отдельный
PostgreSQL 16. Недоступная БД считается ошибкой проверки; подмены SQLite нет.
Проверенный срез от 08.10.2026:

| Проверка | Результат |
|---|---|
| Backend, включая PostgreSQL и фоновые задания | 388 passed; два предупреждения testcontainers |
| Frontend | 189 passed; TypeScript и ESLint passed |
| Production build, Docker, миграции и healthchecks | Passed, проверено в отдельном локальном окружении |
| Источник → сбор → Qwen → решение → повторная обработка | Passed на реальных материалах |
| Браузерная доступность | 22 axe-прогона без нарушений; две темы, 320 px, клавиатура, forced-colors, увеличение текста |

NVDA, VoiceOver/TalkBack, нативный browser zoom и полный ручной проход
перед публичным запуском остаются отдельной приёмкой. Подробности и границы
проверок — в [плане реализации](docs/implementation_plan.md) и
[News Analyzer](docs/news_analyzer.md#подтверждённая-приёмка-08102026).

## Контент

Контент (статьи, заметки, проекты) — Markdown-файлы с frontmatter в
`backend/content/`, редактируются только через git. Формат —
`docs/content_format.md`.

Источники новостей, результаты анализа и решения редактора хранятся
в PostgreSQL отдельно от опубликованного контента. Редакционный центр
не создаёт статьи автоматически и не меняет Markdown.

После обновления Markdown на production выполнить
`bash scripts/publish-content.sh`: backend перечитает файлы, Next.js обновит
кэш и sitemap без пересборки. Подробности и первоначальный запуск —
в [инструкции развёртывания](docs/deployment.md).

## Дизайн и работа с репозиторием

Обязательное дизайн-ТЗ — [BKS_Lab_frontend_design_spec.md](BKS_Lab_frontend_design_spec.md).
Используются светлые поверхности, navy/cyan, отдельная тёмная тема и
существующие брендовые ассеты из `frontend/public/brand/`. Фирменные
изображения лежат в `frontend/public/images/`; исходные референсы —
в `референсы/`. Исторический `generate_placeholders.py` не запускать поверх
готовых ассетов: он перезаписывает файлы заглушками.

Правила для следующих изменений — в [AGENTS.md](AGENTS.md). Локальные env,
ключи, БД, резервные копии, `node_modules`, `.venv` и `.next` не входят в Git.
В репозитории хранятся только примеры конфигурации без рабочих секретов.
