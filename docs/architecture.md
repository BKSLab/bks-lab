# BKS Lab — архитектура

**Версия:** 0.8 (News Analyzer и редакционный центр в существующей админке)
**Статус:** базовый сайт реализован; News Analyzer проходит интеграционную
приёмку. Состояние проверок и оставшаяся приёмка — в
`docs/implementation_plan.md`, развёртывание — в `docs/deployment.md`.

## 1. Цель и границы

Личный сайт bks-lab.ru:

- Главная `/` — лендинг (hero, направления, проекты, последние статьи,
  заметки на полях).
- Блог `/blog` + страница статьи `/blog/post/[slug]`, категории через URL.
- Заметки `/notes` — лента коротких заметок (§3, «Типы контента»).
- Проекты `/projects` + страница проекта `/projects/[slug]`.
- Статические страницы `/about`, `/contacts` (+ `/privacy` с этапа 6).
- Админка `/admin` — **собственный фронт** (дашборды, статистика, контент,
  подписчики), вход по паролю; только для владельца.
- Редакционный центр `/admin/news` — сбор внешних публикаций, LLM-оценка,
  подборки для статей и коротких новостей, решения редактора. Он хранит
  найденные материалы отдельно от опубликованного Markdown.
- Рекламные блоки Яндекс.РСЯ — в блоге и ленте заметок (§4 «Реклама»).

Архитектурное требование владельца: **разделение backend (Python) и frontend
(React)** с самого начала. Бэкенд — источник данных (статьи, заметки,
проекты, категории) через REST API + сбор статистики + закрытое Admin API;
фронтенд их потребляет.

### Что сознательно НЕ делаем (в отличие от референсного проекта)

| Подсистема референса                | Решение для BKS Lab                              |
| ----------------------------------- | ------------------------------------------------ |
| ИИ-агент «Вера», RabbitMQ, SSE      | Не нужно                                         |
| JWT-аутентификация пользователей    | Не нужно (нет пользователей; админка — 1 админ, серверная сессия) |
| sqladmin                            | Не используем — своя админка (§3, §4)            |
| Агрегация вакансий, избранное       | Не нужно                                         |
| Sentry                              | Опционально, этап 9                              |
| Два nginx (frontend + backend)      | Один nginx: `/api` → backend, всё остальное → frontend |

PostgreSQL 16, slowapi, Alembic — **берём из референса** (см. §3).

## 2. Общая схема

```text
браузер
   │ 443 (TLS)
   ▼
nginx ─┬─ /api/* ─────────► backend (FastAPI) ──┬─► backend/content/*.md (источник истины)
       │   (включая /api/admin/*)               └─► PostgreSQL (контейнер db):
       ├─ /admin, /, /blog, … ─► frontend (Next.js, ISR/SSG)      page_views, subscribers,
       │                                  │ серверные fetch       content_items, admin_sessions
       │                                  └──────────────────────► backend (API_INTERNAL_URL)
       ▼
certbot (Let's Encrypt)

news-analyzer-scheduler ──► PostgreSQL (news_*: задания, материалы, анализы)
          └──────────────► RSS/HTML-источники и API внешней LLM
```

- Next.js получает данные от FastAPI **на серверной стороне** (ISR/SSG),
  браузер напрямую в FastAPI не ходит, кроме форм, статистики и Admin API —
  те идут через `/api` под тем же доменом, поэтому CORS в prod не нужен
  (dev — см. §5).
- Бэкенд не рендерит HTML и не отдаёт статику фронтенда.
- FastAPI служит закрытым фасадом News Analyzer под `/api/admin/news`.
  Отдельного HTTP-сервера и новых открытых портов у анализатора нет.

## 3. Backend

### Стек

Python 3.12, FastAPI, Hypercorn, Pydantic v2 + pydantic-settings,
**SQLAlchemy 2 (async) + asyncpg + Alembic**, **PostgreSQL 16**,
slowapi (rate-limit), aiosmtplib (форма «Связаться»),
APScheduler (только отдельный процесс News Analyzer),
httpx + pytest + testcontainers для тестов. Версии фиксируются в
`requirements.txt` при инициализации (ориентир — `requirements.txt`
референсного проекта).

### Архитектура

Слоистая, по `docs/FASTAPI_PATTERNS.md`. Из паттернов переносим структуру и
приёмы, **но не языковое соглашение**: идентификаторы, комментарии,
докстринги и логи — английский (AGENTS.md); emoji-префиксы в логах не
используем. При конфликте с текстом FASTAPI_PATTERNS.md приоритет у этого
правила и AGENTS.md.

```text
backend/
  main.py           # точка входа: hypercorn main:app (пакет src импортируется из корня backend/)
  src/
    api/            # роутеры: articles.py, notes.py, projects.py, categories.py,
                    # stats.py, feedback.py, admin/ (auth.py, stats.py, content.py, subscribers.py)
    services/       # бизнес-логика: ArticleService, NoteService, ProjectService,
                    # StatsService, AdminAuthService, ...
    repositories/   # Markdown*Repository (файлы), StatsRepository,
                    # ContentItemRepository, AdminSessionRepository (SQLAlchemy)
    db/             # engine/session (asyncpg), models/, alembic/ (миграции)
    dependencies/   # DI: db_session.py, repositories.py, services.py, auth.py (require_admin)
    background_tasks/  # периодические задачи: ретенция статистики, чистка просроченных сессий
    schemas/        # Pydantic-схемы запросов/ответов
    core/           # settings (pydantic-settings), логирование
    exceptions/     # доменные исключения со status_code/detail
    utils/          # markdown-парсинг (frontmatter, рендеринг в HTML)
  content/
    articles/       # *.md с frontmatter
    notes/          # *.md — короткие заметки
    projects/       # *.md с frontmatter
  scripts/          # new_article.py, new_project.py, new_note.py
  tests/
  requirements.txt
  Dockerfile
```

Цепочка: `Endpoint → Service → Repository → {Markdown-файлы | PostgreSQL}`.
Правила:

- Эндпоинты тонкие: валидация входа (Pydantic), вызов сервиса, перевод
  доменных исключений в HTTPException.
- Репозиторий — единственное место, знающее про хранилище (файловая система
  или SQLAlchemy). Замена хранилища не трогает сервисы и API.
- DI — через `Annotated[..., Depends(...)]` в `dependencies/`; это же шов
  для API-тестов через `app.dependency_overrides`.
- Конфиг — pydantic-settings, `.env` в корне backend, доступ через
  `@lru_cache get_settings()`. `SecretStr` — только для реальных секретов:
  пароль БД, SMTP-пароль, пароль админки, `stats_secret` (мастер-секрет
  хэширования посетителей), `revalidate_secret` (вебхук фронтенда, §4).
- Backend работает в **одном воркере Hypercorn**: in-memory кэш контента и
  счётчики slowapi — per-process; горизонтальное масштабирование не
  требуется (§5).

### Типы контента

Три типа, все — Markdown в git, единый pipeline парсинга:

| Тип      | Каталог             | Страница              | Frontmatter                                |
| -------- | ------------------- | --------------------- | ------------------------------------------ |
| Статья   | `content/articles/` | `/blog/post/[slug]`   | полный (`docs/content_format.md`)          |
| Заметка  | `content/notes/`    | лента `/notes` (якорь)| усечённый: title, published_at, tags, related |
| Проект   | `content/projects/` | `/projects/[slug]`    | полный проектный                           |

**Заметки** («заметки на полях») — короткие материалы (1–3 абзаца) без
обложки, категории и заголовков в теле. Отдельных страниц в v1 нет: лента
`/notes` с якорями `#note-<slug>`, блок последних заметок на главной и в
сайдбаре блога. Поле `related` связывает заметку со статьёй.

### Хранение контента и процесс публикации — РЕШЕНИЕ

**Утверждено: Markdown-файлы в git — источник истины для всех типов
контента (как в референсном проекте).**

Процесс добавления публикации:

1. Скрипт-генератор (`backend/scripts/new_article.py`, `new_project.py`,
   `new_note.py`) создаёт `<slug>.md` с шаблоном валидного frontmatter.
2. Текст пишется в IDE с Markdown-предпросмотром.
3. Публикация: `git push` → на сервере deploy-скрипт делает `git pull`
   (content смонтирован volume'ом) и вызывает revalidate-вебхук фронтенда
   (§4 «Стратегия рендеринга»). Backend перечитывает файлы по mtime — в API
   материал виден сразу; на сайте — после revalidate (секунды) или очередного
   ISR-окна. Перезапуск и пересборка не требуются.

### Механика синхронизации контента (кэш + проекция)

Протокол обновления in-memory кэша и read-model `content_items` — единый:

- **Триггер:** при первом запросе API после TTL (5 с) проверяется mtime
  каталогов контента; изменение → рескан соответствующего типа.
- **Single-flight:** рескан выполняется под `asyncio.Lock`; параллельные
  запросы не запускают второй рескан. При первом заполнении они дожидаются
  готового кэша или получают ошибку синхронизации вместо пустого ответа.
- **Полный рескан типа:** парсинг всех файлов типа; `content_hash`
  пропускает неизменённые файлы при записи в БД.
- **Одна транзакция:** upsert изменённых + удаление записей исчезнувших и
  ставших невалидными файлов — атомарно. При ошибке БД кэш не обновляется,
  повтор при следующем триггере (кэш и проекция не расходятся).
- **Draft:** файлы с `draft: true` синхронизируются в `content_items` со
  `status=draft` (видны в админке), но исключаются из публичного API и
  поиска. `archived` — только у проектов. Файл, не прошедший валидацию,
  удаляется из кэша и проекции, ошибка логируется.
- **Ошибки файловой системы:** отсутствующий или недоступный каталог/файл
  не считается удалённым контентом: сохраняются предыдущие кэш и проекция,
  при холодном старте возвращается ошибка. Синтаксически повреждённый YAML
  считается невалидным отдельным файлом и не прерывает обработку остальных.
- **`reading_time`** вычисляется из `word_count` (200 слов/мин, минимум 1)
  для всех типов; поле `reading_time` во frontmatter статей — опциональный
  override.

### Проекция контента в БД — РЕШЕНИЕ

**Утверждено владельцем: метаданные и текст контента дублируются в
PostgreSQL для админки и будущего анализа моделями/агентами.**

Это **read-model, а не источник истины**: файлы → проекция, никогда наоборот.

- Таблица `content_items`: `id`, `type` (`article|note|project`), `slug`,
  `title`, `category` (nullable — только статьи), `tags` (JSONB),
  `published_at`, `reading_time` (nullable — статьи/заметки),
  `status` (`active|draft|archived`), `word_count`, `content_text`
  (plain text из Markdown — для анализа), `content_hash`, `synced_at`.
  Уникальность: `(type, slug)`.
- Связь со статистикой: `page_views.path` + `page_views.note_slug`
  сопоставляются с `content_items.slug` по правилам из `api_contract.md`
  (`/blog/post/<slug>`, `/projects/<slug>`, `/notes` + `note_slug`).
- **Точка роста под анализ агентами:** таблица `agent_insights`
  (`content_item_id`, `kind`, `model`, `payload` JSONB, `created_at`) —
  связь закладываем в модели `content_items`, саму таблицу и воркеры
  не строим в текущем плане.

### Статистика — РЕШЕНИЕ

**Утверждено владельцем: PostgreSQL 16 в отдельном контейнере, как в
референсном проекте; статистика — со старта.**

- **PostgreSQL 16** (`postgres:16-alpine`) — отдельный сервис `db` в
  docker-compose (healthcheck `pg_isready`, volume `pg_data`), конфигурация
  через `backend/.env`. Подключение — async SQLAlchemy + asyncpg.
- **Alembic** — миграции схемы, прогон при старте контейнера backend
  (`alembic upgrade head` в entrypoint, как в референсе).
- Модели: `page_views`, `subscribers` (этап P1), `content_items` (проекция),
  `admin_sessions` (админка).
- **`page_views`**: `id`, `viewed_at`, `path` (без query и якоря),
  `note_slug` (nullable — якорь `#note-<slug>` из ленты заметок),
  `referrer_domain` (nullable, max 255), `visitor_hash`.
  Индексы: `(viewed_at)`, `(path, viewed_at)`. Партиционирование не
  требуется; при превышении ~5 млн строк — ежемесячная чистка старых записей
  через `background_tasks/`.
- Приватность статистики: IP и User-Agent не храним.
  `visitor_hash = sha256(daily_salt + ip + ua)`, где
  `daily_salt = HMAC_SHA256(stats_secret, текущая_дата_UTC)` — мастер-секрет
  статичен в `.env`, «соль суток» детерминированно выводится из даты
  (переживает рестарты, фоновая ротация не нужна). Текущая дата получается
  через инъецируемую функцию (тестируемость).
- Следствие ротации (осознанное ограничение): уники считаются только в
  пределах суток; «уники за период» в админке — сумма дневных уников
  (завышена за счёт повторных визитов в разные дни).
- IP клиента — из `X-Forwarded-For`/`X-Real-IP`, которые проставляет nginx;
  backend доверяет им только при подключении от явно разрешённого прокси
  (`APP_TRUSTED_PROXIES`, JSON-массив IP/CIDR; по умолчанию `[]`). Проверяется
  реальный ASGI peer. Цепочка `X-Forwarded-For` разбирается справа налево до
  первого недоверенного адреса; `X-Real-IP` используется только при отсутствии
  XFF. Некорректная цепочка не принимается — используется адрес peer (§5).
- Сбор: фронтенд отправляет `POST /api/v1/stats/pageview`
  (`navigator.sendBeacon`, Blob `application/json`). Insert выполняется в
  фоне (FastAPI BackgroundTasks), ответ 202 сразу. Rate-limit через slowapi.

### Админка: аутентификация и Admin API — РЕШЕНИЕ

**Утверждено владельцем: собственная админка (кастомный фронт, §4) вместо
sqladmin — ради дашбордов, графиков и расширяемости.** Backend предоставляет
закрытое Admin API:

- Все эндпоинты `/api/admin/*` (кроме `login`) — за dependency
  `require_admin` (`dependencies/admin.py`); без валидной сессии — 401.
  Контракт — `docs/api_contract.md` раздел «Admin API».
- **Сессия:** `POST /api/admin/auth/login` (логин/пароль из `.env`,
  постоянно-временное сравнение `secrets.compare_digest`) ставит cookie
  `admin_session`: **httpOnly + Secure + SameSite=Strict, Path=/**, случайный
  токен (32 байта). Серверная сторона — таблица `admin_sessions`
  (`token_hash`, `created_at`, `expires_at`, `last_seen_at`): токен в БД
  хэширован, сессию можно отозвать. TTL 12 ч, скользящее продление.
  Path=/ позволяет серверным страницам `/admin` получить cookie. Активная
  вкладка периодически обращается к `/api/admin/auth/me`, чтобы продление
  cookie дошло до браузера; в скрытой вкладке polling отсутствует.
  Logout удаляет сессию. Регистрации, восстановления пароля, второго
  пользователя — нет.
- **Rate-limit** на login — 5/мин с IP; ответ на неверные креды всегда
  одинаковый (401 `{"detail": "Invalid credentials"}`).
- **CSRF:** login/logout и редакционные изменения защищены SameSite=Strict + проверкой
  заголовка `Origin` на всех небезопасных методах `/api/admin/*` по точному
  списку `ADMIN_ALLOWED_ORIGINS`. Host запроса не является источником доверия.
- Все ответы Admin API, включая ошибки, имеют `Cache-Control: no-store`.
- Просроченные сессии чистятся фоновой задачей (`background_tasks/`).
- Публичное API (`/api/v1`) не отдаёт никаких админских данных.

### News Analyzer: сбор и редакционный анализ

Основание: `search_news/BKS_Lab_News_Analyzer_TZ.md`, каталог
`search_news/BKS_Lab_AI_Sources_Research.md` и согласованные уточнения в
`docs/news_analyzer.md`. Это отдельный поток найденных материалов:
`content_items` и Markdown публикаций не редактируются. Автопубликации нет.

- **API:** `src/api/news.py` → `NewsAdminService` → репозитории `news_*`.
  Все маршруты находятся под `/api/admin/news`, используют существующие
  `require_admin`, Origin-проверку и `Cache-Control: no-store`.
- **Хранилище:** миграция `0004` после `0003` добавляет источники,
  темы/рубрики и связи, материалы, анализы, решения, задания, историю
  обходов, настройки и состояние расписания. Markdown остаётся источником
  истины для публикаций сайта; источники и редакционные данные — PostgreSQL.
- **Фон:** процесс `python -m src.background_tasks.news_scheduler` в
  сервисе `news-analyzer-scheduler` из backend-образа. APScheduler не
  запускается в HTTP-воркерах. Расписание по умолчанию — трижды в сутки,
  `08:00`, `14:00`, `20:00`, `Europe/Samara`. Интервал нового источника —
  6 часов; политика и расписание могут переопределяться в БД через админку.
- **Очередь:** HTTP создаёт задание в PostgreSQL и возвращает 202 с ID.
  Получение задания атомарное (`FOR UPDATE SKIP LOCKED`), с lease,
  heartbeat и ограниченными повторными попытками. Координация расписания
  использует advisory lock и сохраняемое состояние. Операции с внешними
  сервисами не держат транзакции БД; после рестарта задания восстанавливаются.
- **Сбор:** RSS/Atom с ETag/Last-Modified и 304, HTML со списком
  CSS-селекторов. Перед сохранением источника нужен успешный `discover`
  с предпросмотром. Проверяются DNS, каждый redirect, публичность адреса,
  robots.txt, тип и размер ответа; JS не исполняется. Сопоставление GUID,
  нормализованного URL и хеша текста предотвращает повторный разбор
  неизменённых материалов и отмечает совпадения между источниками.
- **LLM:** адаптированный `clients/llm.py` из
  `vera_rag_service/LLM_CLIENT_REFERENCE.md`; провайдер внешний. Модель
  задаётся `NEWS_LLM_MODEL`, URL и ключ — серверными env. Текущий локальный
  профиль — Polza, `qwen/qwen3-30b-a3b-instruct-2507`. Ответ проходит
  Pydantic-валидацию; темы и рубрики выбираются по существующим ID,
  итоговые два рейтинга рассчитываются сервером по весам. Учёт расходов,
  токенные счётчики и бюджетные ограничения не реализуются.
- **Отказоустойчивость:** сбор и анализ разделены; отсутствие ключа или
  ошибка модели сохраняют материал в `pending_analysis`. Есть ограничения
  объёма, таймауты и retries, ручной повторный анализ, очистка старых
  текстов и истории. В интерфейс и ошибки не попадают ключ и тела ответов
  провайдера.
- **Начальные справочники:** `python -m scripts.seed_news` добавляет темы
  и рубрики, не создавая источники. Адреса каталога служат подсказками;
  сохранение и включение каждого источника требуют проверки редактором.

Celery, Redis/RabbitMQ, локальные модели, платные поисковые API, генерация
статей и SEO не входят в этот MVP. Эксплуатационные детали и приёмка —
`docs/news_analyzer.md` и дополнительный этап 10 плана реализации.

### Формы (этап P1)

- `POST /api/v1/feedback` — форма «Связаться»: aiosmtplib, rate-limit,
  honeypot-поле против спама. При отсутствии SMTP или ошибке доставки — 503;
  успешный ответ выдаётся после принятия сообщения SMTP-сервером.
- `POST /api/v1/subscribe` — подписка: email в таблицу `subscribers`
  (идемпотентно), honeypot, rate-limit; список виден в админке.
  Механика рассылок не строится.

### Возможная эволюция (вне текущего плана)

- Публикация: **admin upload-эндпоинт** (`POST /api/admin/content`, приём
  `.md` + изображений в `content/`) — естественное расширение Admin API и
  админки; или git-based CMS (Keystatic/TinaCMS). Источник истины остаётся
  Markdown.
- Анализ контента агентами — таблица `agent_insights` + витрина в админке.

## 4. Frontend

### Стек — УТВЕРЖДЕНО владельцем (отклонение от дизайн-ТЗ §2)

Дизайн-ТЗ §2 указано «React + JavaScript», роутинг React Router «если SPA»,
стили «CSS Modules либо принятая CSS-система». Владельцем утверждён вариант
«как лучше по SEO и технической эффективности»:

- **Next.js 16 (App Router) + React 19 + TypeScript** — как в референсе.
- **Tailwind CSS 4** + дизайн-токены в CSS custom properties (палитра ТЗ §3).
- Тесты: Vitest + Testing Library + vitest-axe.

Обоснование: блог и портфолио критично зависят от SEO (ТЗ §15: уникальные
title/description, canonical, Open Graph на каждую страницу) — Next.js даёт
SSG/ISR, Metadata API, sitemap из коробки; SPA на React Router это всё
отдаёт на клиент и требует отдельного решения для пререндера. Tailwind —
«принятая CSS-система» в терминах ТЗ.

### Структура

```text
frontend/
  src/
    app/
      (public)/                # публичная часть (общий layout сайта)
        page.tsx               # главная (+ блок «Заметки на полях»)
        blog/page.tsx          # список статей
        blog/page/[page]/page.tsx    # пагинация блога путём
        blog/[category]/page.tsx
        blog/post/[slug]/page.tsx
        notes/page.tsx         # лента заметок
        notes/page/[page]/page.tsx
        projects/page.tsx
        projects/[slug]/page.tsx
        about/page.tsx
        contacts/page.tsx
        privacy/page.tsx       # политика конфиденциальности (нужна для РСЯ)
      (admin)/
        admin/login/page.tsx   # вход (публична)
        admin/page.tsx         # дашборд: карточки + графики
        admin/content/page.tsx # материалы (content_items + просмотры)
        admin/subscribers/page.tsx
        admin/news/            # подборки, источники, справочники, задания, настройки
      api/revalidate/route.ts  # on-demand revalidation (секрет)
      sitemap.ts
      robots.ts                # закрывает /admin и /api
      error.tsx, not-found.tsx
    components/{layout,navigation,projects,blog,notes,ads,admin,ui}/
    lib/{api,admin-api,news-api,constants,utils}/
    styles/tokens.css          # палитра и токены из ТЗ §3
  public/{brand,images,og}/    # slots из ТЗ §5–§7, §15 (placeholders)
  Dockerfile
```

> Примечание по URL статьи: ТЗ §11 задаёт `/blog/<category>` для категорий.
> Чтобы не было коллизии `категория vs slug` на одном сегменте, статья живёт
> на `/blog/post/[slug]`, категории — на `/blog/[category]`. Слаг `page`
> зарезервирован под пагинацию и запрещён для категорий.

> Расширения ТЗ, согласованные владельцем: раздел «Заметки» (`/notes`),
> пункт «Заметки» в header (после «Блог») и footer; админка `/admin`;
> рекламные блоки РСЯ. Утверждённая структура главной и блога из ТЗ не
> меняется.

### Стратегия рендеринга и инвалидации

Противоречие «SSG» ↔ «публикация без передеплоя» решено так:

- **ISR как основа:** на всех контентных страницах и списках
  `export const revalidate = 300` (5 мин); `generateStaticParams` прогревает
  существующие slug; `dynamicParams = true` — новый slug после билда
  рендерится on-demand при первом запросе и кэшируется.
- **On-demand revalidation для мгновенной публикации:** route handler
  `app/api/revalidate/route.ts` с секретом (`revalidate_secret`) вызывает
  `revalidateTag`/`revalidatePath`. Все запросы `lib/api` помечены
  `next: { tags: ['articles' | 'notes' | 'projects'] }`. Deploy-скрипт после
  `git pull` вызывает `scripts/publish-content.sh`. Webhook принимает
  `Authorization: Bearer <REVALIDATE_SECRET>` (не менее 32 случайных символов),
  секрет не передаётся в URL. Скрипт сначала обновляет файловый кэш backend,
  затем сбрасывает теги/пути Next.js и прогревает основные страницы и sitemap.
- **SSR (`force-dynamic`) отклонён** для публичных страниц. **Админка —
  наоборот, динамическая** (`force-dynamic` на страницах `(admin)`): данные
  всегда свежие, кэширование не нужно, доступ всё равно закрыт.
- `sitemap.ts` — под тем же ISR/revalidate.
- **Build-time устойчивость:** `next build` в Docker выполняется без
  работающего backend — `lib/api` при недоступности API во время билда
  возвращает пустые списки (`generateStaticParams → []`); страницы
  дорисовываются по ISR на первых запросах.

### Fetch-клиент и надёжность API

- Тонкий типизированный клиент в `lib/api`: `ApiError` с status, таймаут
  5 с (`AbortSignal.timeout`), `next: { revalidate, tags }` на всех запросах.
- 404 от API → `notFound()`; 5xx/таймаут → throw → `error.tsx`.
- Дедупликация запросов между `generateMetadata` и `page()` — встроенная
  дедупликация `fetch` в рамках рендера (при необходимости React `cache()`).
- Два базовых URL: `API_INTERNAL_URL` (`http://backend:8000`, только
  server-side, без `NEXT_PUBLIC_`); клиентские вызовы (поиск, формы,
  статистика, Admin API) — относительный `/api/...` через nginx.
- Админский клиент `lib/admin-api`: те же правила, но без кэширования
  (`cache: 'no-store'`), с обработкой 401 → редирект на `/admin/login`.

### Админка (фронт)

- Route group `(admin)` с собственным минимальным layout (без публичного
  header/footer сайта; стили — те же дизайн-токены).
- **Защита маршрутов:** страницы `(admin)` — server components, каждая
  проверяет сессию через `GET /api/admin/auth/me` (server-side fetch с
  пробросом cookie); 401 → `redirect('/admin/login')`. Клиентских
  «псевдозащищённых» страниц нет.
- **Дашборд:** карточки (просмотры сегодня/7д/30д, уники сегодня),
  графики временных рядов (просмотры/уники по дням), топ страниц и
  referrer'ов, таблица материалов с просмотрами, список подписчиков.
- **Графики:** Recharts, подключается через `next/dynamic` только на
  админских роутах — в бандл публичных страниц не попадает (ТЗ §20).
- **Редакционный центр:** `/admin/news/items` (фильтры и два формата),
  `/items/[id]` (разбор и решения), `/sources`, `/sources/new`,
  `/sources/[id]`, `/topics` (темы и рубрики), `/settings`, `/runs`,
  `/jobs/[id]` — все относительно `/admin/news`. Каждая серверная страница
  проверяет сессию и использует `force-dynamic`/`adminFetch` без кэша.
  Изменения отправляются браузером в same-origin Admin API; долгие операции
  отслеживаются polling по ID задания, 401 возвращает на вход. Источник
  сохраняется с `discovery_job_id`; изменение URL/селекторов требует новой
  проверки. Настройки показывают только безопасный статус и имя модели.
- Форма логина: labels, ошибки текстом, rate-limit сообщение; пароль не
  логируется и не сохраняется в состоянии дольше сабмита.
- A11y админки — WCAG 2.2 AA: labels, focus, текстовые ошибки, статусы для
  скринридеров, две темы, reflow 320 px и применимые пункты дизайн-ТЗ §22.
  Автоматические проверки не заменяют ручную приёмку скринридерами.

### Ключевые паттерны (переносятся из референса)

- SSG/ISR (`generateStaticParams`) + `generateMetadata` (canonical,
  Open Graph) для статей и проектов; `metadataBase` из env — с этапа 2.
- JSON-LD: `schema.org/Article` — только для статей; `BreadcrumbList` —
  для страниц с хлебными крошками. Проекты в v1 без JSON-LD.
  `lastmod` в sitemap — из `published_at`.
- HTML контента от бэкенда санитизируется (isomorphic-dompurify).
- A11y: SkipLink, `<main id="main-content">`, `<html lang="ru">`.
- Изображения — `next/image` с width/height (ТЗ §20, LCP hero —
  `loading="eager"` и `fetchPriority="high"`); шрифты — `next/font/local`
  (Inter + JetBrains Mono из `src/assets/fonts`, WOFF2 с сокращённым набором
  символов для латиницы и русского текста, `display: swap`). OFL-лицензии,
  закреплённые исходники и порядок воспроизведения указаны в README шрифтов.
- Дизайн-токены ТЗ §3 — в `styles/tokens.css` как CSS custom properties;
  Tailwind маппится на них.

### Навигация: фокус, title, трекер

- `document.title` обновляет Metadata API — закрывает ТЗ §21.
- **Фокус при клиентской навигации:** компонент `FocusManager` (client)
  в корневом layout по смене `usePathname()` ставит фокус на H1 страницы
  (`tabindex="-1"`) — дефолту App Router не доверяем. Якорь на заметку
  (`/notes#note-<slug>`): целевой элемент `tabindex="-1"` + программный
  фокус после перехода. Несуществующий или скрытый якорь даёт fallback
  на H1. Первичная загрузка и изменение только query не перехватывают фокус;
  прокрутка, в том числе Back/Forward, остаётся у браузера и Next.js.
- Мобильное меню закрывается при уходе фокуса за пределы кнопки и панели,
  не меняя новый фокус; Escape закрывает его с возвратом на кнопку.
  Раскрытая панель не должна перекрывать фокус в основном содержимом и футере.
- **`PageViewTracker`** (client, в публичном layout — в админке статистика
  не собирается): по смене `usePathname()`/`useSearchParams()` в `useEffect`
  отправляет beacon; дедупликация двойного выстрела StrictMode — ref-флаг
  по значению пути; якорь читается из `window.location.hash` в момент
  отправки; `referrer` отправляется только с первым публичным pageview
  в текущем документе, включая переходы через 404 и повторный mount оболочки;
  тело — `new Blob([json], { type: 'application/json' })`.
  Переход только по якорю внутри уже открытой страницы отдельный pageview
  не создаёт; отдельный учёт таких переходов — решение для этапа 4.

### Реклама (Яндекс.РСЯ)

- Компонент `AdSlot` (client): обёртка `<aside aria-label="Реклама">`,
  **фиксированная высота под конкретно выбранный формат РСЯ** (не
  адаптивный формат — иначе CLS; форматы и высоты выбираются на этапе 7 и
  вписываются в документ). Загрузчик РСЯ — один раз глобально через
  `next/script` (`strategy="lazyOnload"`), не из каждого слота.
- Слоты: сайдбар блога (после «Популярных тем»), конец статьи (после
  контента, не внутри текста), лента `/notes` — не чаще одного слота на
  экран. **Главная и админка — без рекламы.**
- В dev и при выключенном флаге `NEXT_PUBLIC_ADS_ENABLED` слот не
  рендерится вообще (никаких пустых контейнеров).
- CSP под РСЯ требует `script-src`/`frame-src`/`connect-src`/`img-src` с
  доменами Яндекса и, вероятно, `unsafe-inline` в `script-src` — это
  осознанный компромисс. Старт — `Content-Security-Policy-Report-Only`,
  финальная политика утверждается на этапе 7 с живой рекламой.
- Рекламные iframe РСЯ могут не иметь `title` (внешний код, не исправить) —
  зафиксировано как известное исключение в чек-листе доступности (этап 8).
- РСЯ модерирует только живой домен: заявка и активация — после запуска
  (этап 7). До активации слоты отключены флагом.

### Тестирование фронтенда

- Компоненты получают данные пропсами; fetch изолирован в `lib/api` и
  тонких server-обёртках — это шов для моков (мок `lib/api` или
  `global.fetch`).
- Юнит-тесты: `lib/api` (таймаут, маппинг 404/5xx), `PageViewTracker`
  (мок sendBeacon, дедуп по pathname), `AdSlot` (флаг on/off).
- a11y-тесты vitest-axe на ключевых компонентах (header, карточки, формы).

## 5. Инфраструктура

```text
docker-compose.yml
  db         # postgres:16-alpine, healthcheck pg_isready, volume pg_data
  backend    # FastAPI + hypercorn, 1 воркер, entrypoint: alembic upgrade head + старт,
             # volume: content/ (контент); env из backend/.env
  news-analyzer-scheduler # тот же backend-образ, APScheduler + очередь, без ports
  frontend   # Next.js standalone, мультистейдж Dockerfile, non-root
  nginx      # 80/443, TLS: /api/* → backend:8000 (включая /api/admin/*),
             # всё остальное (включая /admin) → frontend:3000
  certbot    # Let's Encrypt webroot
```

Сервис `db` — по образцу референса:

```yaml
db:
  image: postgres:16-alpine
  env_file: ./backend/.env
  restart: always
  volumes:
    - pg_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
    interval: 10s
    timeout: 5s
    retries: 5
```

- Имя БД задаётся стандартной переменной `POSTGRES_DB` (её и использует
  healthcheck); приложение читает тот же DSN из `.env`.
- Порт БД наружу не публикуем в prod (в dev можно `5434:5432` для
  подключения из IDE, как в референсе).
- Один nginx (упрощение референсной схемы с двумя).
- nginx проставляет `X-Forwarded-For`/`X-Real-IP`; backend доверяет им
  только от адресов nginx из `APP_TRUSTED_PROXIES`. Разбор заголовков выполняет
  `src/utils/http.py`; Hypercorn сохраняет реальный адрес peer. При запуске
  без прокси список остаётся пустым. В prod разрешаются конкретные адреса
  nginx, а не все клиенты или вся общая сеть контейнеров; backend не имеет
  публичного порта. nginx перезаписывает `X-Real-IP` адресом `$remote_addr`
  и добавляет его в `X-Forwarded-For`.
- nginx-конфиг через envsubst-шаблон, как в референсе.
- **Security-заголовки — только в nginx** (единое место: CSP
  Report-Only→enforce, HSTS, X-Frame-Options); `next.config.ts` их не
  дублирует. Для `/admin` — более строгий CSP (без доменов РСЯ).
- `backend/content/` — volume: обновление контента = `git pull` на сервере,
  без пересборки образа. Deploy-скрипт после `git pull` вызывает
  `/api/revalidate` фронтенда (§4).
- Dev-режим: `docker compose up db backend news-analyzer-scheduler` + локально `next dev`; в dev
  `next.config.ts` содержит rewrites `/api/* → http://localhost:8000`
  (CORS не нужен и локально; Admin API доступен на том же origin).

## 6. Нефункциональные требования

- **WCAG 2.2 AA** — обязательно для публичной части (ТЗ §14, чек-лист §22,
  DoD §23); админка — WCAG 2.2 AA в применимой части.
- Производительность: ТЗ §20 (LCP hero — `next/image priority`, размеры
  изображений, шрифты через `next/font`; трекер статистики — sendBeacon;
  реклама — lazyOnload, фиксированная высота слотов, на главной отсутствует;
  Recharts — только в админском бандле).
- SEO: ТЗ §15 (title/description, canonical, OG, sitemap, robots.txt;
  JSON-LD для статей; пагинация путём для индексации страниц 2+).
  `/admin` и `/api` закрыты от индексации в robots.txt.
- Безопасность: security-заголовки в nginx (§5); rate-limit на формах,
  статистике и `/api/admin/auth/login`; админ-сессия — httpOnly + Secure +
  SameSite=Strict cookie, серверные сессии с хэшированным токеном и TTL;
  проверка Origin на мутациях; секреты только через `.env`; БД недоступна
  снаружи в prod; Admin API не смешан с публичным (отдельный префикс
  `/api/admin`, отдельный роутер, обязательная dependency `require_admin`).
- Приватность: статистика без IP и cookies, хэш посетителя с дневной солью
  (HMAC от даты); страница `/privacy` (обязательна для РСЯ).

## 7. Открытые вопросы

Решённые: стек фронтенда (Next.js 16 + TS + Tailwind 4); хранение
публикаций (Markdown в git); БД (PostgreSQL 16 отдельным контейнером);
админка (**собственный фронт + Admin API**, серверные сессии); заметки
(третий тип контента, `/notes`); реклама (РСЯ через `AdSlot`, активация
после запуска); стратегия рендеринга (ISR + on-demand revalidate).

Открытые:

- Подписка: сбор email в БД — решено; нужна ли отправка рассылок — за
  рамками текущего плана.
- Домен/хостинг: где будет жить prod (для TLS и metadataBase, нужно к этапу 7).
- Форматы и высоты рекламных блоков РСЯ — выбираются на этапе 7.
- Анализ контента моделями/агентами (`agent_insights`) — направление
  зафиксировано, объём и сроки не определены. News Analyzer (этап 10)
  анализирует внешние публикации отдельно от этой будущей проекции сайта.
