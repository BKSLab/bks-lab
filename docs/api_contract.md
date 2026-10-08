# BKS Lab — контракт REST API

**Версия:** 0.8 (добавлен закрытый News Analyzer API)
**Базовый URL:** публичное API — `/api/v1`; Admin API — `/api/admin`
(prod — тот же домен через nginx, CORS не требуется)

## Общие соглашения

- Формат: JSON, кодировка UTF-8.
- Ошибки — стандартный FastAPI-формат: `{"detail": "..."}` с кодом из таблицы
  ошибок эндпоинта. Ошибки валидации — 422 с массивом `detail[]` (формат
  FastAPI).
- Пагинация: query `page` (>= 1, default 1), `page_size` (1–50, default 10).
  Ответ — объект `Paged<T>`. `page` за пределами диапазона → 200 с
  `items: []` (не 404).
- Сортировка списков — по дате desc, tiebreaker `slug` asc (детерминированно).
- Даты — ISO 8601 (`2026-02-10`), время чтения — минуты, целое >= 1
  (вычисляется из word_count, 200 слов/мин, если не задан override).
- Кэш-заголовки публичного API: списки — `Cache-Control: public, max-age=60`;
  детальные — `ETag` от `content_hash`. `no-store` не выставлять (ломает
  fetch-кэш Next). Admin API — `Cache-Control: no-store` на всём.

## Модели (публичные)

### ArticleSummary

```json
{
  "slug": "1c-async",
  "title": "Как мы вынесли синхронизации 1С в отдельный асинхронный контур",
  "excerpt": "Аннотация 1–3 предложения",
  "category": "development",
  "published_at": "2026-02-10",
  "reading_time": 8,
  "cover_image": "/images/articles/1c-async.webp",
  "tags": ["1C", "async", "architecture"]
}
```

### ArticleDetail (= ArticleSummary +)

```json
{
  "...": "все поля ArticleSummary",
  "content_html": "<p>Отрендеренный и безопасный HTML статьи</p>",
  "seo": {
    "title": "…",
    "description": "…",
    "og_image": "/og/bks-lab-default.jpg"
  }
}
```

`content_html` рендерится на бэкенде из Markdown; фронтенд дополнительно
санитизирует (isomorphic-dompurify) — защита в глубину. `seo.og_image`
по умолчанию — `/og/bks-lab-default.jpg` (fallback, если во frontmatter
`og_image` не задан); per-article OG (`/og/articles/<slug>.jpg`) — опционально.

### Note

```json
{
  "slug": "small-team-deploys",
  "title": "Почему маленькие команды деплоят чаще",
  "excerpt": "Первый абзац заметки как plain text (вычисляется)",
  "published_at": "2026-02-12",
  "reading_time": 1,
  "tags": ["management", "deploy"],
  "related_article": {
    "slug": "1c-async",
    "title": "Как мы вынесли синхронизации 1С в отдельный асинхронный контур"
  },
  "content_html": "<p>Короткий текст заметки</p>"
}
```

`excerpt` — первый абзац тела, plain text (вычисляется при парсинге).
`related_article` — null, если поле `related` не задано или статья не
найдена (битая ссылка логируется, заметка остаётся в выдаче). Отдельной
страницы у заметки нет — только лента `/notes` с якорем `#note-<slug>`.

### ProjectSummary / ProjectDetail

```json
{
  "slug": "work-for-everyone",
  "title": "Работа для всех",
  "excerpt": "Платформа с вакансиями для людей с инвалидностью и AI-помощником.",
  "cover_image": "/images/projects/work-for-everyone.webp",
  "tags": ["FastAPI", "Next.js", "PostgreSQL", "AI"],
  "status": "active",
  "featured": true,
  "order": 1
}
```

`ProjectDetail` добавляет `content_html` и `seo` (как у статьи, с тем же
OG-fallback). `status`: `active | archived`. `featured: true` — показывать
на главной, сортировка по `order`.

### Category

```json
{ "slug": "development", "title": "Разработка", "articles_count": 12 }
```

Фиксированный стартовый набор (ТЗ §11): `development` (Разработка), `ai` (AI),
`management` (Управление), `thoughts` (Мысли), `accessibility` (Инклюзия).
Слаг `page` зарезервирован под пагинацию и не может быть категорией.

### Paged<T>

```json
{ "items": [], "total": 42, "page": 1, "page_size": 10, "pages": 5 }
```

## Публичные эндпоинты (`/api/v1`)

### GET /articles

Список статей, сортировка `published_at` desc, `slug` asc.

Query: `page`, `page_size`, `category` (slug, опц.), `q` (опц.).

- `q`: `min_length=2` (иначе 422). Поиск регистронезависимый, по подстроке
  в title/excerpt/тексте, по in-memory кэшу — черновики (`draft`) в выдачу
  и поиск не попадают.
- Неизвестная `category` → 200 с пустой выдачей (не 404).

200 → `Paged<ArticleSummary>`. 422 — невалидные параметры.

### GET /articles/latest

Для главной: последние N статей. Query: `limit` (1–10, default 3).

200 → `ArticleSummary[]`.

### GET /articles/{slug}

200 → `ArticleDetail`. 404 — статья не найдена или `draft`.

### GET /notes

Лента заметок, сортировка `published_at` desc, `slug` asc.

Query: `page`, `page_size` (default 20 — заметки короткие).

200 → `Paged<Note>`.

### GET /notes/latest

Для блока «Заметки на полях» на главной и в сайдбаре блога.
Query: `limit` (1–10, default 3).

200 → `Note[]`.

### GET /categories

200 → `Category[]` (включая категории с нулём статей — для фильтров блога).

### GET /projects

Query: `featured` (bool, опц. — `true` для главной).
Сортировка: `order` asc, tiebreaker `slug` asc.

200 → `ProjectSummary[]`.

### GET /projects/{slug}

200 → `ProjectDetail`. 404 — проект не найден или `draft`.

### POST /stats/pageview

Сбор статистики посещений (отправляется из `PageViewTracker` через
`navigator.sendBeacon` с телом `new Blob([json], { type: 'application/json' })`
— `text/plain` не принимается).

Request:

```json
{ "path": "/blog/post/1c-async", "referrer": "https://google.com/" }
```

- `path` — обязателен, относительный путь сайта (max 500 символов).
  Валидируется по белому списку шаблонов маршрутов: `/`, `/blog…`,
  `/notes…`, `/projects…`, `/about`, `/contacts`, `/privacy`.
  Пагинация блога поддерживает `/blog/page/N` и `/blog/<category>/page/N`.
  Неподходящий `path` → **202 без записи** (не 422, чтобы не обучать ботов).
- Нормализация перед записью: query-string обрезается; якорь вида
  `#note-<slug>` на `/notes` и `/notes/page/N` извлекается в отдельную
  колонку `note_slug`; в `path` остаётся путь страницы без query и якоря
  (`/notes` либо `/notes/page/N`). На других страницах `note_slug = null`.
  Slug заметки допускает 1–200 символов по правилам `content_format.md`;
  невалидный или слишком длинный якорь даёт `note_slug = null`, сам
  просмотр разрешённой страницы сохраняется.
- `referrer` — опционально; хранится только домен (max 255), невалидное
  значение → null. Клиент шлёт его только с первым публичным pageview
  текущего документа; клиентские переходы и повторный mount публичной
  оболочки не сбрасывают этот признак.

Сервер ставит insert в фоне (BackgroundTasks) и отвечает сразу.
Сохраняет в PostgreSQL (`page_views`): `viewed_at`, `path`, `note_slug`,
`referrer_domain`, `visitor_hash = sha256(daily_salt + ip + user_agent)`,
где `daily_salt = HMAC_SHA256(stats_secret, текущая_дата_UTC)`.
IP и User-Agent в БД не хранятся. Запросы с User-Agent известных ботов
отбрасываются.

- 202 → без тела (accepted)
- 422 — отсутствует или невалиден формат `path` (несоответствие белому
  списку — это 202 без записи, см. выше)
- 429 — rate-limit (60/мин с IP)

### POST /feedback  *(этап P1)*

Форма «Связаться».

Request:

```json
{ "name": "Иван", "email": "ivan@example.com", "message": "Текст", "website": "" }
```

`website` — honeypot: непустое значение → 200 `{"status": "sent"}` без
отправки (молча отбрасываем).

- 200 → `{"status": "sent"}`
- 422 — валидация (name 1–100, email до 254, message 10–5000 символов;
  имя и сообщение очищаются от пробелов по краям)
- 429 — rate-limit превышен (5/час с IP)
- 503 — SMTP не настроен или доставка не удалась. Успех возвращается
  после SMTP-доставки, а не постановки в ненадёжную фоновую задачу.

Адрес получателя и отправителя берётся только из `SMTP_RECIPIENT` и
`SMTP_SENDER`; email посетителя используется как `Reply-To`. Сообщение
и имя в PostgreSQL не сохраняются. `website` ограничен 2000 символами.

### POST /subscribe  *(этап P1)*

Request: `{"email": "ivan@example.com", "website": ""}`.
`website` — honeypot, как в `/feedback`.
Email сохраняется в PostgreSQL (таблица `subscribers`, видна в админке).
Повторная подписка того же email — 200 (идемпотентно, без раскрытия факта
дубля). Email нормализуется: пробелы по краям удаляются, регистр приводится
к нижнему, международный домен — к IDNA. Хранятся только email и время
первой подписки; повторный запрос не изменяет это время.
200 → `{"status": "subscribed"}`. 422 — невалидный email.
429 — rate-limit (5/час с IP).

### GET /api/health  *(вне `/api/v1`)*

Выполняет `SELECT 1` к PostgreSQL.
200 → `{"status": "ok"}`. 503 → `{"status": "unavailable"}` при
недоступности БД. Для healthcheck в docker-compose и nginx.

## Admin API (`/api/admin`, закрытое)

Все эндпоинты, кроме `POST /auth/login`, требуют валидную админ-сессию
(cookie `admin_session`, проверка dependency `require_admin`).
Без сессии или с просроченной → **401** `{"detail": "Not authenticated"}`.
Все ответы, включая ошибки, — `Cache-Control: no-store`. Все небезопасные
методы, включая POST и PATCH редакционного центра, проверяют
единственный заголовок `Origin` по явно настроенному списку
`ADMIN_ALLOWED_ORIGINS` (JSON-массив точных origin со схемой и портом,
без завершающего `/`). Пустой список, отсутствующий/повторный заголовок
или несовпадение → 403. Заголовок `Host` не определяет доверенный origin.
Пагинация Admin API: `page_size` по умолчанию 20, максимум 50.

### Аутентификация

**POST /auth/login**

Request: `{"username": "…", "password": "…"}` (логин/пароль из `.env`,
сравнение `secrets.compare_digest`).

- 200 → `{"status": "ok"}` + `Set-Cookie: admin_session=<token>; HttpOnly;
  Secure; SameSite=Strict; Path=/; Max-Age=43200`.
  Серверная сессия в `admin_sessions` (`token_hash`, TTL 12 ч, скользящий).
- 401 → `{"detail": "Invalid credentials"}` — одинаковый ответ на неверный
  логин и пароль.
- 429 — rate-limit (5/мин с IP).

`ADMIN_USERNAME` и `ADMIN_PASSWORD` обязательны для входа; пустые значения
закрывают доступ, готового пароля по умолчанию нет. Токен состоит из 32
случайных байт в base64url; в БД хранится SHA-256, токен никогда не входит
в JSON. Повторный вход заменяет сессию текущего браузера. Просроченные
записи удаляются периодической задачей.

`Path=/` нужен, чтобы cookie приходила на SSR-страницы `/admin` в Next.js.
Каждый успешный защищённый запрос продлевает срок в БД и возвращает
обновлённую cookie. Браузерный `GET /auth/me` нужен для продления cookie
после SSR, поскольку серверный fetch Next.js сам не пересылает Set-Cookie
посетителю. `ADMIN_COOKIE_SECURE=false` допустим только для локального HTTP;
по умолчанию Secure включён.

**POST /auth/logout** — удаляет сессию. 204, cookie сбрасывается.

**GET /auth/me** — проверка сессии (используется страницами `(admin)`
server-side). 200 → `{"username": "…"}`. 401 — нет/просрочена.

### Статистика

**GET /overview** — карточки дашборда:

```json
{
  "views_today": 123, "views_7d": 800, "views_30d": 3200,
  "uniques_today": 45,
  "top_pages_30d": [{"path": "/blog/post/1c-async", "views": 300}],
  "top_referrers_30d": [{"domain": "google.com", "views": 120}]
}
```

**GET /stats/timeseries** — графики. Query: `metric` (`views|uniques`),
`period` (`7d|30d|90d`, default 30d).
200 → `[{"date": "2026-02-10", "value": 42}]`.
`uniques` — дневные уники (за период сумма дневных, завышена — осознанное
приватностное ограничение).

Все периоды включают текущий календарный день UTC и предыдущие N−1 дней;
события из будущего не учитываются. Ряд содержит каждую дату периода,
включая дни с нулём событий. Для overview применяются те же границы;
`top_pages_30d` и `top_referrers_30d` содержат до 10 строк.

**GET /stats/pages** — таблица страниц. Query: `period` (как выше), `page`,
`page_size`. 200 → `Paged<{path, note_slug, views, uniques}>`,
сортировка views desc.
`uniques` здесь также означает сумму дневных уникальных посетителей.
При равенстве просмотров порядок: path asc, note_slug asc (null первым).

**GET /stats/referrers** — Query: `period`. 200 → `[{domain, views}]`,
топ-50, сортировка views desc.

### Контент

**GET /content** — материалы из `content_items` (включая `draft`).
Query: `type` (`article|note|project`, опц.), `status`
(`active|draft|archived`, опц.), `q` (подстрока в title до 100 символов,
без учёта регистра, `%`/`_` не являются wildcard), `page`, `page_size`.
Пустой `q` не фильтрует. Порядок: published_at desc (null последними), id desc.
Перед чтением проверяется актуальность всех трёх Markdown-проекций.
200 → `Paged<ContentItemRow>`:

```json
{
  "id": 1, "type": "article", "slug": "1c-async",
  "title": "…", "category": "development", "tags": ["…"],
  "published_at": "2026-02-10", "status": "active",
  "word_count": 1600, "views_30d": 300
}
```

**GET /content/{id}** — карточка материала: все поля `ContentItemRow` +
`synced_at`, `content_hash` и `views_timeseries_30d`
(`[{date, value}]`). 404 — нет такого id.

Просмотры статьи связываются с `/blog/post/<slug>`, проекта — с
`/projects/<slug>`, заметки — с `note_slug` на всех страницах ленты.
Просмотр ленты без якоря не приписывается отдельной заметке.

### Подписчики

**GET /subscribers** — Query: `page`, `page_size`.
200 → `Paged<{email, subscribed_at}>`, сортировка по дате desc,
при равенстве времени — email asc.

### Редакционный центр (`/news`)

Полный префикс — **`/api/admin/news`**. Эти маршруты управляют источниками,
найденными публикациями и редакционными решениями. `/content` остаётся
витриной Markdown только для чтения; News Analyzer не создаёт публикации
на сайте. Cookie, `require_admin`, Origin-проверка и `no-store` применяются
ко всему разделу. ID — положительные целые числа; даты ответов — ISO 8601
UTC. Лишние поля в запросах запрещены. В PATCH передаются изменяемые поля;
`null` для них не допускается.

| Метод и путь после `/api/admin/news` | Результат |
|---|---|
| GET `/sources` | 200, массив `SourceRow` |
| POST `/sources/discover` | 202, `QueuedJob` |
| POST `/sources` | 201, `SourceRow` |
| PATCH `/sources/{id}` | 200, `SourceRow` |
| GET `/topics`, GET `/categories` | 200, массив `CatalogRow` |
| POST `/topics`, POST `/categories` | 201, `CatalogRow` |
| PATCH `/topics/{id}`, PATCH `/categories/{id}` | 200, `CatalogRow` |
| GET `/items` | 200, `Paged<ItemRow>` |
| GET `/items/{id}` | 200, `ItemDetail` |
| POST `/items/{id}/decision` | 200, `DecisionRow` |
| POST `/items/{id}/reanalyze` | 202, `QueuedJob` |
| POST `/jobs/collect` | 202, `QueuedJob` |
| GET `/jobs/{id}` | 200, `JobRow` |
| GET `/runs` | 200, `Paged<RunRow>` |
| GET `/settings`, PATCH `/settings` | 200, `SettingsRow` |

`Paged<T>` содержит `items`, `total`, `page`, `page_size`, `pages`.
Для `/items` и `/runs` по умолчанию `page=1`, `page_size=20`, максимум 50.
Источники и справочники возвращают массивы без пагинации.

#### Источники и предпросмотр

`POST /sources/discover` принимает:

```json
{"url": "https://example.org/feed.xml", "kind": "rss", "config": {}}
```

`kind` необязателен: адаптер определяет RSS/Atom или HTML. Разрешённые
значения — `rss`, `html`; URL — http/https, без учётных данных и фрагмента.
`config` допускает только непустые CSS-селекторы длиной до 500 символов:
`item_selector`, `title_selector`, `link_selector`, `date_selector`,
`content_selector`. Внешняя проверка выполняется worker-процессом.

Ответ сразу: `{"job_id": 9, "status": "queued"}`. После `completed`
в `GET /jobs/9` поле `result` содержит `kind`, итоговый `url`, `items`
(до пяти публикаций: `title`, `url`, `published_at`, необязательный
`excerpt`) и `warnings`. Ошибка проверки не разрешает сохранение источника.

`POST /sources` принимает проверенные `url`, `kind`, `config`, название
`name` (1–200 символов), обязательный `discovery_job_id` и параметры:

| Поле | Ограничения / значение API по умолчанию |
|---|---|
| `active` | boolean, true; форма нового источника предлагает включение явно |
| `priority`, `trust_score` | целые 0–100, 50 |
| `vendor_affiliated` | boolean, false |
| `interval_hours` | целое 1–720, 6 |
| `topic_ids`, `category_ids` | до 50 существующих положительных ID, `[]` |

Проверка должна завершиться успешно для той же конфигурации и типа.
URL может совпадать с исходным URL проверки или найденным URL ленты;
в БД сохраняется найденный адрес. Изменение `url`, `kind` или `config`
через PATCH тоже требует `discovery_job_id`; изменение названия,
приоритета, активности или справочников не требует нового обхода.
Пауза источника — `PATCH /sources/{id}` с `{"active": false}`.

`SourceRow` содержит ID, все сохранённые поля источника, `topic_ids`,
`category_ids`, `last_success_at`, `last_error`, `last_new_count`, `health`.
В ответ не включаются внутренний cursor и параметры lease.

#### Темы и рубрики

Создание: `{"name":"AI Engineering","description":"Практическая разработка","active":true}`.
Название — 1–120 символов, описание — до 3000, по умолчанию пустое;
`active` по умолчанию true. PATCH меняет любые из этих полей. `CatalogRow`
содержит `id`, `name`, `description`, `active`. Выключение записи сохраняет
историю существующих анализов. Совпадение уникального названия — 409.

#### Подборки, анализ и решения

`GET /items` поддерживает фильтры `source_id`, `category_id`, `topic_id`,
`format` (`longread_candidate` / `short_news_candidate`), `status`
(`pending_analysis` / `analyzed`), `decision` (`in_work` / `deferred` /
`rejected`), `min_score` (0–100), `date_from`, `date_to`, `page`, `page_size`.
Период относится к `first_seen_at`, обе границы включены и должны содержать
часовой пояс; начало позже окончания — 422. Фронтенд переводит выбранные
дни в начало и конец суток UTC.

Без фильтра `format` доступны материалы, ожидающие анализа. Формат и
рубрики/темы фильтруются по текущему анализу, решение — по последней записи.
Рейтинг для `longread_candidate` — `article_score`, в остальных случаях —
`news_score`; сортировка по нему убывает, null в конце. При равенстве —
`first_seen_at desc`, затем `id desc`.

`ItemRow`: `id`, `source_id`, `source_name`, `url`, `canonical_url`
(nullable), `title`, `excerpt`, `published_at`, `first_seen_at`,
`last_seen_at`, `updated_at`, `status`, `duplicate_of_id`, `analysis`
(nullable), `decision` (nullable). `ItemDetail` добавляет `content`,
`analysis_history`, `decision_history`.

Анализ содержит `id`, `is_relevant`, `category_id`, `category_name`,
`topics` (массив `CatalogRow`), `suggested_topics` (отдельные строки),
`scores`, `summary_ru`, `editorial_comment_ru`, `recommended_formats`,
`confidence` (0–1), `needs_verification`, `news_score`, `article_score`,
`model`, `prompt_version`, `created_at`. Критерии `scores` —
`topical_fit`, `significance`, `freshness`, `article_potential`, каждый 0–100.
Итоговые рейтинги вычисляет сервер; анализ не заменяет проверку фактов.

`POST /items/{id}/decision`:

```json
{"decision":"in_work","format":"longread_candidate","comment":"Проверить цифры по первоисточнику"}
```

`comment` необязателен, до 2000 символов. Ответ `DecisionRow` добавляет
`id`, `item_id`, `editor`, `created_at`. Редактор определяется по сессии,
передать его через тело запроса нельзя. Решения сохраняются как история.
`POST /items/{id}/reanalyze` не требует тела и ставит отдельное задание
повторного анализа; содержимое Markdown не меняется.

#### Задания и история обходов

`POST /jobs/collect` принимает `{}` для активных источников либо
`{"source_id":7}` для одного источника. Длительные операции возвращают
`QueuedJob` сразу; они не зависят от открытой вкладки браузера.

`JobRow`: `id`, `kind` (`collect` / `discover` / `analyze`), `status`
(`queued` / `running` / `completed` / `failed` / `cancelled`), `source_id`,
`item_id`, `attempts`, `progress`, `error`, `result`, `created_at`,
`started_at`, `completed_at`, `heartbeat_at`. `progress` при сборе содержит
`sources_total`, `sources_done`, `new`, `updated`, `unchanged`, `errors`.
`result` проверки источника описан выше; у остальных стадий это итог стадии.
Ключ провайдера, тело его ответа и токен владения заданием не выдаются.

`GET /runs` дополнительно принимает `source_id`. `RunRow`: `id`,
`source_id`, `source_name`, `job_id` (nullable после очистки истории),
`status`, `started_at`, `completed_at`, `new_count`, `updated_count`,
`unchanged_count`, `error`. Это история попыток обхода, не список публикаций.

#### Настройки

GET возвращает действующие настройки; PATCH сохраняет переданные поля.
Параметры политики и расписания в PostgreSQL переопределяют env-значения
по умолчанию:

| Поле | Ограничения / значение по умолчанию |
|---|---|
| `enabled` | boolean, true |
| `timezone` | IANA time zone, `Europe/Samara` |
| `schedule` | ровно три разных HH:MM, `08:00`, `14:00`, `20:00` |
| `editorial_policy` | 1–12000 символов |
| `exclusions` | до 6000 символов |
| `news_weights`, `article_weights` | четыре целых веса 0–100, сумма каждого набора 100 |
| `initial_lookback_days` | 1–365, 30 |
| `max_items_per_source` | 1–200, 50 |
| `max_excerpt_chars` | 500–12000, 3000 |
| `analysis_batch_size` | 1–200, 20 |
| `text_retention_days` | 1–3650, 90 |
| `history_retention_days` | 1–3650, 180 |

Ключи весов: `topical_fit`, `significance`, `freshness`, `article_potential`.
Для новостей по умолчанию 40/25/25/10, для статей — 35/25/10/30.
GET дополнительно возвращает безопасные `llm_configured`, `llm_provider`,
`llm_model`; PATCH их не принимает. `llm_configured` означает наличие
серверной конфигурации, а не результат проверки доступности провайдера.
Модель выбирается через `NEWS_LLM_MODEL`, URL/ключ остаются только на сервере.
Полей учёта расходов, токенных счётчиков и бюджетов в API нет.

Общие ошибки редакционного API: 401 — нет сессии; 403 — Origin не разрешён;
404 — запись отсутствует; 409 — конфликт записи или нет подходящего
успешного discover; 422 — неверные поля, справочники, веса или период.
Сообщения ошибок ограничены безопасными пояснениями без ответов провайдера
и секретов. Эксплуатация — [news_analyzer.md](news_analyzer.md).

## Нефункционально

- Rate-limit (slowapi) на публичных формах, статистике pageview и
  `/api/admin/auth/login`; на GET — не требуется.
- Ответы списков контента должны укладываться в < 100 мс локально
  (контент кэшируется в памяти).
- Backend работает в одном воркере (in-memory кэш и slowapi per-process).
