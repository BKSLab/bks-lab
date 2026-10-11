# Интеграция статистики РСЯ и LLM-анализа в админку

План реализации раздела «Реклама» в собственной админке BKS Lab: сбор
статистики Яндекс Партнёрского интерфейса (РСЯ), склейка с внутренней
статистикой посещений и анализ данных внешней LLM по запросу.

Статус: проектное предложение, согласовано направление. Реализация имеет
смысл до включения РСЯ, но реальные данные появятся только после запуска
рекламы (владелец отложил публичный запуск и включение РСЯ — этот документ
не возвращает те шаги в активную работу).

## Что уже есть

### Реклама на фронтенде

- `frontend/src/components/ads/AdSlot.tsx` — клиентский компонент рекламного
  блока: `<aside aria-label="Реклама">` фиксированной высоты (анти-CLS),
  ленивая загрузка `https://yandex.ru/ads/system/context.js` через
  `next/script`, поддержка тёмной темы, destroy при размонтировании.
- `frontend/src/lib/ads.ts` — три плейсмента: `blog-sidebar`, `article-end`,
  `notes-feed`. Env-флаги: `NEXT_PUBLIC_ADS_ENABLED` +
  `NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID` / `_ARTICLE_ID` / `_NOTES_ID`
  (валидация формата `R-[A-Z]-\d+-\d+`). Без валидного ID слот не
  рендерится.
- Блоки встроены в страницы блога, статьи и заметок; упоминание в политике
  конфиденциальности. Тесты: `frontend/tests/ad-slot.test.tsx`.

### Статистика посещений (своя)

- Публичный сбор: `POST /api/v1/stats/pageview` (`backend/src/api/stats.py`),
  запись в фоне, фильтр ботов и белый список путей.
- Приватность: IP и User-Agent не хранятся; уникалы считаются подневно по
  `visitor_hash = sha256(HMAC(stats_secret, дата) + ip + ua)`.
- Таблица `page_views` (`backend/src/db/models/page_views.py`).
- Админские эндпоинты (все за `require_admin`, read-only) в
  `backend/src/api/admin.py`: `/api/admin/overview`,
  `/api/admin/stats/timeseries`, `/api/admin/stats/pages`,
  `/api/admin/stats/referrers`.
- Страницы админки: `/admin` (обзор: счётчики, график, топы),
  `/admin/stats/pages`, `/admin/stats/referrers`. Графики — Recharts
  (`AdminTimeSeries` / `AdminTimeSeriesChart`).

### Админка (каркас)

- Route-group `frontend/src/app/(admin)/admin/`, навигация в
  `frontend/src/components/admin/AdminShell.tsx`; серверные компоненты с
  `requireAdmin()` + `adminFetch` (`frontend/src/lib/admin-api/index.ts`).
- Аутентификация: один админ из env, opaque-токен сессии (sha256-хэш в БД,
  TTL 12 ч, скользящее продление), httpOnly-cookie `admin_session`
  (SameSite=strict), rate-limit логина, `check_admin_origin` для мутаций.
- Общие UI-кирпичи: `AdminFilters` (период 7d/30d/90d), `AdminPagination`,
  `AdminTimeSeries`.

### LLM-клиент

- `backend/src/clients/llm.py` — httpx-клиент по референсу
  `vera_rag_service/LLM_CLIENT_REFERENCE.md`: таймауты, ограниченные retries
  с backoff + jitter, различение retryable (429/5xx) и постоянных 4xx,
  валидация ответа Pydantic, логирование без тел провайдера.
- Настройки `NEWS_LLM_*` (`backend/src/core/news_settings.py`),
  `SecretStr`-ключ, свойство `llm_configured`. Провайдер Polza, модель по
  умолчанию `qwen/qwen3-30b-a3b-instruct-2507` (меняется через
  `NEWS_LLM_MODEL`).
- Фабрики ресурсов: `backend/src/dependencies/news_clients.py` —
  `httpx.AsyncClient(trust_env=False)`, при отсутствии ключа фича
  деградирует, не падая.

### Архитектурные паттерны для новых эндпоинтов

- Слои по `docs/FASTAPI_PATTERNS.md`: `api → services → repositories → БД`;
  DI: `dependencies/repositories.py` (Level 1) → `dependencies/services.py`
  (Level 2) с алиасами `XxxServiceDep`.
- Все админские эндпоинты — только под префиксом `/api/admin`, за
  `require_admin`, мутации требуют точный Origin, ответы `no-store`.
- Модели — `backend/src/db/models/`, миграции — Alembic в
  `backend/src/db/alembic/versions/`.
- Тесты: pytest + httpx (backend), Vitest + Testing Library (frontend).

## API Яндекс Партнёрского интерфейса

Документация: <https://yandex.ru/dev/partner-statistics/doc/ru/>.

- Read-only API статистики РСЯ, базовый URL `https://partner.yandex.ru/api/`.
- Авторизация: OAuth-токен аккаунта РСЯ, заголовок
  `Authorization: OAuth <token>`. Токен получается вручную один раз по ссылке
  из раздела «Доступ к API»; OAuth-flow не нужен. Токен API статистики
  отдельный от токена in-app рекламы.
- `GET /api/statistics2/tree` — метаданные аккаунта: доступные уровни
  отчётов, поля-измерения (`dimension_fields`), поля-группировки
  (`entity_fields`), фильтры и метрики (`fields`). Список метрик зависит от
  аккаунта — фиксируется после первого вызова с реальным токеном.
- `GET /api/statistics2/get` — отчёт. Параметры:
  - `lang` (обяз.), `period` — пресеты (`today`, `yesterday`, `thismonth`,
    `lastmonth`, `30days`, `90days`, `180days`, `365days`, `thisyear`) или
    произвольный интервал двумя параметрами `period=<дата>&period=<дата>`;
  - `field` — метрики (несколько параметров; из примеров: `shows`, `hits`,
    `hits_render`, `fillrate`; доходные поля — по дереву аккаунта);
  - `dimension_field` — группировка по времени (`date|day|week|month|year`)
    или географии (`geo|country|area|city`);
  - `entity_field` — группировка по площадкам (`page_id`, `page_caption`),
    блокам (`complex_block_id`, `block_caption`), срезам (`tag_id`), ОС,
    браузерам;
  - `filter` — JSON-фильтры вида `["page_id","=","458472"]`;
  - `order_by`, `limits` (пагинация `{"limit":N,"offset":M}`,
    признак `is_last_page` в ответе);
  - `currency` (RUB по умолчанию), `vat`, `stat_type` (нам нужен `main`).
- Ответ: `points[]` с `dimensions` + `measures`, `totals` по валютам.
- Явные квоты в документации не зафиксированы — закрываемся снапшотами в БД
  и ретраями на 429/5xx.

## Целевой функционал

1. **Дашборд рекламы `/admin/ads`**: счётчики (доход за сегодня/7д/30д),
   график дохода по дням, таблица по рекламным блокам (показы, fill rate,
   CTR, доход), фильтр периода 7d/30d/90d.
2. **Склейка со своей статистикой**: RPM (доход на 1000 просмотров), доход
   на уникального посетителя, совмещённый график «трафик vs доход» —
   метрики, которых нет ни в одном интерфейсе по отдельности.
3. **LLM-анализ по кнопке**: интерпретация текущих данных (динамика,
   аномалии, рекомендации по блокам) — по запросу, без расписания.

## План реализации

### Этап 1. Backend: клиент API Яндекса и настройки

- `backend/src/core/settings.py` (или отдельный модуль настроек):
  `YANDEX_PARTNER_OAUTH_TOKEN` (`SecretStr`, `repr=False`), таймаут/retries
  с границами; свойство `ads_configured` — готовность без раскрытия секрета.
- `backend/src/clients/yandex_partner.py` по образцу `clients/llm.py`:
  `httpx.AsyncClient(trust_env=False)`, заголовок `Authorization: OAuth`,
  таймаут на запрос, retries только на 429/5xx, валидация ответа
  Pydantic-схемами, свои исключения (`backend/src/exceptions/`), без тел
  ответов в логах.
- Методы клиента: `get_tree()` (метаданные) и `get_report(...)` с типизированными
  параметрами (period, fields, dimension/entity fields, filters).
- Первый прогон `statistics2/tree` с реальным токеном — зафиксировать
  доступные идентификаторы метрик (особенно доходные поля) в этом документе
  или в env-конфиге.
- `backend/.env.example` — новые переменные с комментариями.
- Тесты клиента: мок httpx, успех/429/5xx/4xx/таймаут, отсутствие токена.

### Этап 2. Хранение и сбор снапшотов

- Модель `ads_daily_stats` (`backend/src/db/models/`): дата, идентификатор
  блока/среза, показы, запросы, отрисовки, fill rate, клики, CTR, доход
  (RUB); уникальный ключ (дата, блок). Миграция Alembic.
- Репозиторий `backend/src/repositories/ads_stats.py`: upsert за диапазон
  дат, выборки для дашборда.
- Сервис сбора `backend/src/services/ads_sync.py`: запрос
  `statistics2/get` за последние N дней (N ≈ 7–14, т.к. Яндекс пересчитывает
  недавние дни), разрез по дням и блокам, перезапись снапшотов.
- Запуск: раз в сутки фоновой задачей (по аналогии с
  `background_tasks/admin_sessions.py`; альтернатива — перенести в
  scheduler News Analyzer, где уже есть очередь и lease). Плюс ручной
  триггер `POST /api/admin/ads/sync` для отладки.
- Без токена сбор пропускается с записью в лог (без падения).
- Тесты: репозиторий (upsert/выборки), сервис (мок клиента, перезапись
  недавних дней, идемпотентность).

### Этап 3. Backend: API дашборда

- Эндпоинты (все за `require_admin`, GET, `no-store`):
  - `GET /api/admin/ads/overview` — счётчики дохода/показов за
    сегодня/7д/30д, средний fill rate;
  - `GET /api/admin/ads/timeseries?metric=revenue|shows&period=7d|30d|90d` —
    серия по дням с заполнением нулевых (переиспользовать подход
    `services/admin_stats.py`);
  - `GET /api/admin/ads/blocks?period=...` — таблица по рекламным блокам;
  - `GET /api/admin/ads/rpm?period=...` — склейка с `page_views`: RPM,
    доход на уникального посетителя, серия «трафик vs доход».
- Схемы `backend/src/schemas/` (Pydantic v2, Literal для периодов/метрик),
  сервис `backend/src/services/admin_ads.py`, DI-фабрики.
- Если токен не настроен — эндпоинты возвращают явный ответ о ненастроенной
  интеграции (фронт показывает заглушку).
- Тесты: контракт эндпоинтов, границы периодов, пустые данные, 401 без
  сессии.

### Этап 4. Frontend: страница `/admin/ads`

- `frontend/src/app/(admin)/admin/ads/page.tsx` — серверный компонент,
  `requireAdmin()` + `adminFetch`; ссылка «Реклама» в `AdminShell.tsx`.
- Типы и функции в `frontend/src/lib/admin-api/` (types + парсеры параметров).
- UI: карточки-счётчики, `AdminTimeSeries` для дохода, таблица по блокам,
  совмещённый график «трафик vs доход», `AdminFilters` для периода.
- Заглушка «Интеграция не настроена» при отсутствии токена; состояние
  «данных пока нет» до первого снапшота.
- Доступность по чек-листу дизайн-ТЗ §22: табличная альтернатива графикам,
  подписи, контраст, клавиатурная навигация.
- Тесты Vitest: рендер с данными/без, заглушка без токена.

### Этап 5. LLM-анализ по кнопке

- `POST /api/admin/ads/analysis` (за `require_admin`, `check_admin_origin`,
  `no-store`, rate-limit ~5–10 запросов/час).
- Сервис: собирает компактный дайджест из БД — итоги за 7/30 дней, динамика
  по дням, разрез по блокам, fill rate, RPM и просмотры из `page_views`;
  системный промпт «аналитик монетизации сайта»; только агрегаты, без
  токенов и внутренних ID.
- Ответ модели валидируется Pydantic (резюме + наблюдения + рекомендации);
  при ошибке/отсутствии LLM-ключа — внятный 503.
- Анализы **не сохраняются** в БД (эфемерная интерпретация). Если позже
  понадобится история — отдельная таблица и задача.
- Frontend: кнопка «Анализировать» на `/admin/ads`, спиннер и таймаут на
  время запроса, блокировка повторного клика, карточка с результатом.
- Тесты: сервис (мок LLM-клиента), эндпоинт (503 без ключа, rate-limit),
  фронт (состояния loading/success/error).

### Этап 6. Документация и приёмка

- Обновить `docs/architecture.md` (новый клиент и таблица),
  `docs/api_contract.md` (эндпоинты `/api/admin/ads/*`), этот документ
  (фактические идентификаторы метрик из `statistics2/tree`), README
  (env-переменные), AGENTS.md при изменении зафиксированных там решений.
- Полная приёмка после включения РСЯ: реальный токен, вызов `tree`,
  корректность цифр против Партнёрского интерфейса, работа кнопки анализа
  на реальных данных.

## Ограничения и риски

- РСЯ отключена до production-запуска: реальные данные появятся только после
  её включения. Токен выдаётся в Партнёрском интерфейсе независимо, поэтому
  этапы 1–5 можно собрать и проверить заранее.
- Квоты API в документации не описаны — смягчаем ежесуточными снапшотами,
  кэшем и retries.
- Яндекс пересчитывает статистику за недавние дни — снапшоты за последние
  N дней перезаписываются.
- Наружу (LLM-провайдеру Polza) уходят только агрегированные коммерческие
  данные (доход, показы, RPM) — тот же контур доверия, что уже принят для
  News Analyzer.
- OAuth-токен — только в серверном env, не выдаётся API, не логируется.
