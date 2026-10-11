# News Analyzer — интеграция и эксплуатация

Основание: `search_news/BKS_Lab_News_Analyzer_TZ.md` и каталог источников
`search_news/BKS_Lab_AI_Sources_Research.md`. Реализация MVP: RSS/Atom и HTML,
внешняя LLM, редакционные решения. Найденные материалы не публикуются
автоматически и не изменяют Markdown сайта.

## Обследование перед реализацией

Существующий FastAPI backend уже содержит PostgreSQL, Alembic,
`async_session_factory`, защиту `require_admin`, проверку Origin и no-store
для `/api/admin/*`. Он служит фасадом `news-analyzer-api`; отдельный публичный
API и ещё один сервер не требуются. APScheduler запускается только процессом
`news-analyzer-scheduler` из того же backend-образа. Долговечная очередь
и расписание хранятся в PostgreSQL, а не в памяти HTTP-воркера.

Точки изменения:

- `backend/src/db/models/news_*.py`, миграция после `20261008_1201`:
  источники, темы/рубрики и связи, материалы, анализы, задания, история
  обходов, редакционные решения и настройки.
- `backend/src/repositories/news_*.py`, `services/news_*.py`,
  `schemas/news.py`, `dependencies/news.py`, `api/news.py`, `main.py`:
  слоистый Admin API, короткие транзакции, защищённые изменения.
- `backend/src/clients/news_http.py`, `news_sources.py`, `llm.py`:
  безопасное получение внешних страниц, адаптеры и LLM-клиент.
- `backend/src/core/news_settings.py`, `background_tasks/news_scheduler.py`:
  конфигурация, отдельный scheduler, lease/heartbeat и восстановление.
- `frontend/src/app/(admin)/admin/news/`, `components/admin/news/`,
  `lib/news-api/`: редакционный центр в существующем AdminShell.
- Compose, примеры env, README, API-контракт, план реализации и тесты.

LLM-клиент адаптирован из `vera_rag_service/LLM_CLIENT_REFERENCE.md`.
По прямому поручению владельца локальные параметры провайдера берутся
из `.env` того проекта, профиль фонового обогащения. Секрет копируется
только в игнорируемый `backend/.env`; в документации, API и логах его нет.
По уточнению владельца отдельный учёт расходов, резервирование бюджета
и денежные лимиты не реализуются. Клиент переносится с минимальной
адаптацией; модель задаётся одной переменной env, первоначально недорогая
Qwen при наличии у этого провайдера. Сохраняются обычные таймауты,
ограниченные retries и ограничение числа материалов за один проход.

## Внутренний контракт MVP

Все маршруты ниже имеют префикс `/api/admin/news`, существующие session
cookie, Origin-проверку для изменений и запрет кэширования. ID — целые
положительные числа, даты — ISO 8601 UTC. Пагинация: `items`, `total`,
`page`, `page_size`; максимум 50 строк. Справочники возвращаются массивами.

| Метод и путь | Назначение |
|---|---|
| GET/POST `/sources`, PATCH `/sources/{id}` | Источники, добавление, изменение/пауза |
| POST `/sources/discover` | Поставить проверку/предпросмотр в очередь (202) |
| GET/POST `/topics`, PATCH `/topics/{id}` | Темы |
| GET/POST `/categories`, PATCH `/categories/{id}` | Рубрики |
| GET `/items`, GET `/items/{id}` | Подборки и карточка материала |
| POST `/items/{id}/decision` | Редакционное решение |
| POST `/items/{id}/reanalyze` | Повторный анализ (202) |
| POST `/jobs/collect`, GET `/jobs/{id}` | Ручной сбор (202), прогресс/предпросмотр |
| GET `/runs` | История обходов |
| GET/PATCH `/settings` | Политика, расписание, веса и лимиты |

Асинхронный ответ: `{"job_id": 1, "status": "queued"}`. Задание содержит
`id`, `kind` (`collect`, `discover`, `analyze`), `status`, `source_id`,
`item_id`, `attempts`, `progress`, `error`, `result`, даты и heartbeat.
Ошибки — короткие безопасные сообщения, без тел ответов провайдера.

Источник: `id`, `name`, `url`, `kind` (`rss`/`html`), `config`, `active`,
`priority` (0–100), `trust_score` (0–100), `vendor_affiliated`,
`interval_hours`, `topic_ids`, `category_ids`, `last_success_at`,
`last_error`, `last_new_count`, `health`. HTML `config`: `item_selector`,
`title_selector`, `link_selector`, `date_selector`, `content_selector`.
Discover принимает `url`, необязательный `kind` и `config`; `result`
завершённого задания содержит `kind`, `url`, `items` (до пяти), `warnings`.
Сохранение источника разрешено только после успешного discover этого URL
и конфигурации. Результат проверки явно передаётся как `discovery_job_id`.

Тема/рубрика: `id`, `name`, `description`, `active`. Решение:
`decision` (`in_work`/`deferred`/`rejected`), `format`
(`longread_candidate`/`short_news_candidate`), `comment` (до 2000 символов).
Редактор всегда берётся из сессии, а не из тела запроса.

Карточка списка: `id`, `source_id`, `source_name`, `url`, `canonical_url`,
`title`, `excerpt`, `published_at`, `first_seen_at`, `last_seen_at`,
`updated_at`, `status` (`pending_analysis`/`analyzed`), `duplicate_of_id`,
`analysis` (null либо результат), `decision` (null либо последнее решение).
Анализ: `id`, `is_relevant`, `category_id`, `category_name`, `topics`,
`suggested_topics`, `scores`, `summary_ru`, `editorial_comment_ru`,
`recommended_formats`, `confidence`, `needs_verification`, `news_score`,
`article_score`, `model`, `prompt_version`, `created_at`.
Подробная карточка дополнительно содержит `content`, `analysis_history`
и `decision_history`. Фильтры: `source_id`, `category_id`, `topic_id`,
`format`, `status`, `decision`, `min_score`, `date_from`, `date_to`, `page`.
Без фильтра format показываются и ещё не разобранные материалы.

Настройки: `enabled`, `timezone`, `schedule` (три HH:MM),
`editorial_policy`, `exclusions`, `news_weights`, `article_weights`
(ключи `topical_fit`, `significance`, `freshness`, `article_potential`,
сумма каждого набора 100), `initial_lookback_days`, `max_items_per_source`,
`max_excerpt_chars`, `analysis_batch_size`,
`text_retention_days`, `history_retention_days`. GET дополнительно содержит
безопасные `llm_configured`, `llm_provider`, `llm_model`.
Ключ и URL с учётными данными не выдаются.

## Критерии проверки

Обязательны PostgreSQL-тесты дедупликации, lease/recovery, двух scheduler;
RSS/304/HTML/SSRF/redirect/robots; ошибки и валидация
LLM; авторизация и Origin для всех API; реальные UI-сценарии с клавиатурой,
состояния ожидания/ошибки, две темы и мобильная раскладка. API/парсеры
проверяются на контролируемых фикстурах, не зависящих от внешних сайтов.

## Запуск и повседневная работа

Команды установки, начальные справочники и env приведены в
[README](../README.md#news-analyzer). Backend применяет миграцию `0004`
до запуска scheduler. Оба процесса используют один образ и одну БД;
HTTP-сервер сам очередь не обрабатывает. Для просмотра состояния:

```bash
docker compose ps
docker compose logs --tail 50 news-analyzer-scheduler
```

Во вкладке «Каталог» (`/admin/news/sources/catalogue`) доступны **все 98
позиций** из таблиц разделов 1–7 `search_news/BKS_Lab_AI_Sources_Research.md`:
15 лабораторий, 15 инженерных источников, 11 о бизнесе, 16 об обществе,
16 авторских сайтов, 15 русскоязычных ресурсов и 10 API/поисковых ресурсов.
Повторные упоминания авторов в разных разделах сохранены. Доступны поиск по
названию, описанию и всем URL, фильтры по разделу, приоритету A/B/C и способу
использования. Исходные описания, способы подключения и дополнительные
ссылки перенесены без сокращения; тест сверяет их с Markdown.

Для RSS/Atom и страниц публикаций «Проверить и подключить» открывает
`/admin/news/sources/new?catalogue=<id>` с заполненными названием, адресом,
способом получения и признаком поставщика. API и ресурсы для чтения видны
в том же каталоге с ограничениями подключения; отдельные API-адаптеры не
реализованы. Уже сохранённый URL (включая адрес ленты или альтернативный
адрес из списка) ведёт к настройкам источника и показывает статус сбора.

В `/admin/news/sources/new` также можно указать свой адрес или выбрать
источник из сгруппированного списка. «Проверить источник» создаёт фоновое
задание; после успешного предпросмотра настройте рубрики, темы, доверие и
регулярный сбор, затем
сохраните. Начальный интервал — 6 часов. Проверка только показывает
материалы; их сохранение начинается при ручном или плановом обходе.
Изменение URL, способа получения или CSS-селекторов требует новой проверки.
Выбор другого пункта каталога сбрасывает прежний предпросмотр и результат
проверки. Каталог не создаёт записей в БД и не включает сбор автоматически.

По умолчанию обходы запускаются в `08:00`, `14:00`, `20:00`,
`Europe/Samara`. Расписание и редакционные настройки применяются без
перезапуска, в пределах `NEWS_SETTINGS_REFRESH_SECONDS` (30 секунд).
Пауза источника исключает его из плановых обходов. Выключение общего
расписания также останавливает постановку новых автоматических анализов;
уже взятые задания завершаются. Ручная проверка, сбор выбранного источника
и повторный анализ доступны независимо от этого переключателя.

В «Источниках» над списком доступен блок «Ручная проверка публикаций»:
выберите все активные источники или один выбранный и нажмите «Проверить
сейчас». Задание выполняется в фоне; состояние, счётчики результата и
ссылка на задание появляются под кнопкой. Пока задание выполняется,
повторный запуск из этого блока заблокирован. «История проверок» ведёт в
«Запуски», где также доступен ручной сбор.
Открытую вкладку разрешается закрыть: задание остаётся в PostgreSQL.
Новые материалы сначала сохраняются, затем отдельные задания передают
их модели. «Все материалы» включает ожидающие анализа; «Для статей» и
«Короткие новости» показывают соответствующие рекомендации. В карточке
есть первоисточник, оценки, аннотация и решение редактора.

Локально проверен и включён `https://simonwillison.net/atom/entries/`.
Для приёмки сохранены три настоящих материала; пробное решение «Отложено»
помечено комментарием. Остальные адреса каталога подключаются через тот же
предпросмотр. Seed не создаёт источники и не включает их автоматически.

## Модель и повторная обработка

Текущая локальная модель — `qwen/qwen3-30b-a3b-instruct-2507` через Polza.
Это сменная начальная конфигурация: окончательный выбор остаётся владельцу.
Клиент получает уже собранный текст, а не ищет материалы в интернете.
Версия запроса `news-v2` ограничивает аннотацию 500 символами, комментарий
редактора — 600. Рейтинги рассчитывает Python из проверенных оценок модели.

`NEWS_LLM_API_KEY`, `NEWS_LLM_API_URL`, `NEWS_LLM_MODEL` и
`NEWS_LLM_PROVIDER` задаются только на сервере. После изменения env
пересоздайте backend и scheduler, как показано в README. Статус «Настроена»
означает наличие конфигурации; доступность провайдера проверяется запросом.
Расходные счётчики, денежные квоты и резервирование бюджета отсутствуют.

Одинаковое содержимое повторно не анализируется. Изменение содержимого
создаёт новое задание; старые результаты сохраняются. Изменение модели,
политики или весов само по себе не пересчитывает уже разобранный архив:
используйте «Повторить анализ» в нужной карточке.

Идентичность результата — материал, хеш содержимого, модель и версия
запроса. Явный повтор с той же идентичностью обновляет результат и дату;
факт запуска остаётся в заданиях. Другая модель, версия или содержимое
создают отдельную запись истории. Отдельной версии на каждое нажатие нет.
Редакторские решения сохраняются отдельной историей с автором из сессии.

## Сбои, ограничения и хранение

Без ключа материалы остаются в `pending_analysis`. Ошибки сети, 429/5xx
и некорректный JSON проходят ограниченные повторные попытки. После
исчерпания попыток задание видно как ошибочное; сохранённый материал
доступен для ручного повторного анализа. Постоянные ошибки 4xx не
повторяются внутри клиента. В логах нет ключей, запросов и тел ответов LLM.

При перезапуске scheduler забирает сохранённую очередь; просроченный lease
восстанавливается с учётом лимита попыток. Пока lease действует, второй
процесс не получает это задание. Heartbeat и проверка владельца при записи защищают
от сохранения результата устаревшим обработчиком. Пропущенные слоты
расписания объединяются в последний актуальный обход.

Начальные ограничения: первые 30 дней, до 50 материалов за обход
источника, до 3000 символов фрагмента, до 20 постановок анализа за пакет.
Сбор не обходит robots.txt, защиту сайтов и страницы, требующие JavaScript.
HTML — best effort с настраиваемыми селекторами; сложному сайту нужен
отдельный адаптер. Ошибочный источник не мешает сохранить результаты
успешных источников.

HTTP-клиент принимает `gzip` (включая `x-gzip`) и `deflate` (zlib/raw).
`NEWS_HTTP_MAX_RESPONSE_BYTES` (по умолчанию 2 МиБ) ограничивает **и скачанные,
и распакованные** байты независимо друг от друга. Распаковка потоковая,
с ограничением выделяемого объёма; повреждённые и оборванные потоки
отклоняются. Brotli, Zstandard и многослойное сжатие не поддерживаются.
Проверки DNS/IP, TLS, robots.txt и перенаправлений действуют также для лент
и отдельных страниц материалов. Недоступный robots.txt обозначается
отдельно от явного запрета обхода; ни один из этих случаев не обходится.

При автоматическом разборе HTML используются заголовки и даты карточек,
сохраняются заголовки внутри `article`; навигация и ссылки на файлы не
считаются публикациями. Статический HTML внутри `noscript` можно разобрать
без исполнения JavaScript. Если опубликованная на странице RSS/Atom-лента
недоступна, но HTML содержит карточки, предпросмотр возвращает их с
предупреждением. Явно выбранный RSS не подменяется HTML.

Фоновая очистка выполняется раз в час. По умолчанию текст удаляется через
90 дней без повторного обнаружения, старые задания, обходы и история —
через 180 дней. Последние анализ и редакторское решение сохраняются.
Резервная копия общей БД включает редакционные данные; порядок описан в
[инструкции развёртывания](deployment.md).

## Проверка совместимости каталога

Повторяемый аудит использует тот же `NewsSourceClient` и HTTP-защиты, что
scheduler. Он проверяет все уникальные основные адреса, RSS и дополнительные
ссылки из каталога; дубли авторов сопоставляются с исходными строками.
Справочные сайты и API проверяются на доступность отдельно: HTTP 200 для
документации не означает наличия готового адаптера API.

Из корня проекта (PowerShell, запущен dev Compose):

```powershell
Get-Content -Raw frontend/src/lib/news-api/catalogue.ts | docker compose exec -T backend python -m scripts.audit_news_catalogue --catalogue - --output /tmp/news-catalogue-audit.json --collect
docker compose cp backend:/tmp/news-catalogue-audit.json "$env:TEMP/news-catalogue-audit.json"
```

Это чтение внешних ресурсов без записи источников/материалов в БД и без LLM.
`--collect` дополнительно получает до трёх материалов каждого найденного
источника, включая попытку загрузить текст; для проверки старых блогов
используется окно 3650 дней, рабочая настройка 30 дней не меняется.
Ошибка догрузки текста сохраняется в `collection.warnings`, ошибка этапа
сбора — в `collection.status`; успешный предпросмотр от этого не становится
успешной проверкой текста. Предпросмотр содержит до пяти карточек.
По умолчанию одновременно проверяются до пяти адресов, общий предел на
адрес — 120 секунд; обычные лимиты HTTP-клиента сохраняются. Завершение
команды означает завершение аудита: результаты надо смотреть в `summary`
и `results`, включая `failed`/`error`.

Для адресного повторения: `--only labs-deepmind,labs-anthropic`. Необязательный
`--documents-dir /tmp/news-audit-documents` сохраняет публичные документы
для локального разбора; их не следует добавлять в git. JSON-отчёт содержит
короткие предпросмотры и разрешённые HTTP-заголовки, без cookies и секретов.

### Результаты живого аудита, 08.10.2026

Проверены **98 строк** каталога: **102 исходных уникальных адреса** и четыре
проверенные замены — **106 адресов** суммарно. После исправлений выполнен
полный повторный проход, затем адресная проверка уточнённого OECD.

Из **85 подключаемых строк** (81 уникальный основной URL) **56 прошли
автоматический предпросмотр и сбор**: 30 RSS/Atom и 26 HTML. Ещё **Forbes
прошёл с явными HTML-селекторами**. Получение проверено для **57 из 85**
строк (около 67%); 28 требуют другого адреса/адаптера или доступности сайта.
Это техническая совместимость, не гарантия свежих новостей или полного
текста каждой статьи. Из остальных 13 справочных/API-строк 12 доступны
для чтения, сайт Yann LeCun недоступен. API-адаптеры не добавлялись.

Для всех 106 URL получены 57 предпросмотров с пробными пакетами (168 карточек
с возможными повторами), 12 доступных справочных страниц и 37 безопасных
отказов, включая старые URL и вспомогательные страницы. Forbes дополнительно
проверен пакетом из трёх карточек. У Karpathy и Bengio часть текстов
недоступна; в результатах сохранены карточки с предупреждением. Личные
сайты могут содержать архивные публикации: рабочее окно 30 дней тогда
корректно даёт нулевой сбор. Страница EU AI Act отдаёт также общие новости
Еврокомиссии, CNews — общую бизнес-ленту; тематику надо проверить перед включением.

Исправления проверены на живых примерах: gzip/deflate (включая DeepMind
robots.txt), карточки Anthropic/Meta/Qwen/Worklab, заголовки Google AI/Cohere/
РБК, датированные списки, отсечение меню и продуктовых ссылок. Ошибка
alternate-ленты больше не отменяет корректный HTML-предпросмотр.
У NVIDIA, CNews и DeepSeek заменены устаревшие/неподходящие адреса, у OECD
выбрана лента AI Wonk вместо обзора; прежние ссылки оставлены дополнительными.

Оставшиеся ограничения:

- HTTP 403/429, недоступный robots.txt и остановка передачи не обходятся.
  У METR отдельный запрос с лимитом 60 секунд получил 14298 из 28534 байт,
  хотя последующий общий прогон прошёл: внешняя доступность нестабильна,
  увеличение штатного таймаута не гарантирует успех.
- The Zvi отдаёт ленту больше 2 МиБ; лимит не повышался.
- Часть страниц не содержит подходящих карточек в статическом HTML или
  ведёт к авторизации (TechCommunity). Нужны иной URL либо селекторы/адаптер.
- Для HBR найден [актуальный раздел](https://hbr.org/topic/subject/ai-and-machine-learning?sort=newest),
  для Yudkowsky — [профиль](https://www.lesswrong.com/users/eliezer-yudkowsky),
  для Т-Банка — [AI Research](https://ai.tbank.ru/research/).
  Их безопасная загрузка в дополнительной проверке не прошла;
  эти адреса не помечены готовыми к подключению.

<details>
<summary>Все 98 строк: результат по основному адресу подключения</summary>

| Раздел | Источник | Результат |
|---|---|---|
| Лаборатории | [OpenAI News](https://openai.com/news/) | HTTP 403 |
| Лаборатории | [Anthropic News](https://www.anthropic.com/news) | HTML: 3 карточки |
| Лаборатории | [Google DeepMind](https://deepmind.google/discover/blog/) | HTML: 3 карточки |
| Лаборатории | [Google AI Blog](https://blog.google/technology/ai/) | HTML: 3 карточки |
| Лаборатории | [Hugging Face Blog](https://huggingface.co/blog/feed.xml) | RSS: 3 карточки |
| Лаборатории | [Meta AI](https://ai.meta.com/blog/) | HTML: 3 карточки |
| Лаборатории | [Microsoft Research](https://www.microsoft.com/en-us/research/blog/) | RSS: 3 карточки |
| Лаборатории | [Microsoft Azure AI](https://techcommunity.microsoft.com/category/azure-ai-services/blog/azure-ai-services-blog) | Автоматически карточки не найдены |
| Лаборатории | [Mistral AI News](https://mistral.ai/news) | RSS: 3 карточки |
| Лаборатории | [NVIDIA AI Blog](https://blogs.nvidia.com/blog/tag/artificial-intelligence/) | RSS: 3 карточки |
| Лаборатории | [Cohere Blog](https://cohere.com/blog) | HTML: 3 карточки |
| Лаборатории | [AWS Machine Learning](https://aws.amazon.com/blogs/machine-learning/) | RSS: 3 карточки |
| Лаборатории | [IBM Research AI](https://research.ibm.com/artificial-intelligence) | RSS: 3 карточки |
| Лаборатории | [Qwen](https://qwenlm.github.io/) | HTML: 3 карточки |
| Лаборатории | [DeepSeek](https://www.deepseek.com/en/news/) | HTML: 3 карточки |
| Разработка | [Simon Willison](https://simonwillison.net/atom/entries/) | RSS: 3 карточки |
| Разработка | [Lilian Weng](https://lilianweng.github.io/) | RSS: 3 карточки |
| Разработка | [Chip Huyen](https://huyenchip.com/blog/) | RSS: 3 карточки |
| Разработка | [Hugging Face Papers](https://huggingface.co/papers) | HTML: 3 карточки |
| Разработка | [LangChain Blog](https://blog.langchain.com/) | Автоматически карточки не найдены |
| Разработка | [LlamaIndex Blog](https://www.llamaindex.ai/blog) | Сеть/таймаут |
| Разработка | [arXiv cs.AI](https://rss.arxiv.org/rss/cs.AI) | RSS: 3 карточки |
| Разработка | [arXiv cs.CL](https://rss.arxiv.org/rss/cs.CL) | RSS: 3 карточки |
| Разработка | [arXiv cs.LG](https://rss.arxiv.org/rss/cs.LG) | RSS: 3 карточки |
| Разработка | [Full Stack Deep Learning](https://fullstackdeeplearning.com/) | Автоматически карточки не найдены |
| Разработка | [Eugene Yan](https://eugeneyan.com/) | HTML: 3 карточки |
| Разработка | [Hamel Husain](https://hamel.dev/) | RSS: 3 карточки |
| Разработка | [Sebastian Raschka](https://sebastianraschka.com/blog/) | RSS: 3 карточки |
| Разработка | [Martin Fowler](https://martinfowler.com/feed.atom) | Сеть/таймаут |
| Разработка | [GitHub Blog: AI](https://github.blog/ai-and-ml/) | HTML: 3 карточки |
| Бизнес | [Ethan Mollick / One Useful Thing](https://www.oneusefulthing.org/) | RSS: 3 карточки |
| Бизнес | [MIT Sloan Management Review / AI](https://sloanreview.mit.edu/tag/artificial-intelligence/) | Сеть/таймаут |
| Бизнес | [Harvard Business Review / AI](https://hbr.org/topic/subject/artificial-intelligence) | HTTP 404 |
| Бизнес | [McKinsey / AI](https://www.mckinsey.com/capabilities/quantumblack/our-insights) | Сеть/таймаут |
| Бизнес | [Stanford HAI AI Index 2026](https://hai.stanford.edu/ai-index/2026-ai-index-report) | Сеть/таймаут |
| Бизнес | [Microsoft WorkLab](https://www.microsoft.com/en-us/worklab/) | HTML: 3 карточки |
| Бизнес | [Gartner AI](https://www.gartner.com/en/topics/artificial-intelligence) | HTTP 403 |
| Бизнес | [Deloitte Insights / AI](https://www.deloitte.com/global/en/insights/topics/ai.html) | robots.txt: HTTP 403 |
| Бизнес | [IBM Think / AI](https://www.ibm.com/think/topics/artificial-intelligence) | Автоматически карточки не найдены |
| Бизнес | [VentureBeat AI](https://venturebeat.com/ai/) | HTTP 429 |
| Бизнес | [The Batch (DeepLearning.AI)](https://www.deeplearning.ai/the-batch/) | HTML: 3 карточки |
| Общество | [AI Now Institute](https://ainowinstitute.org/) | HTML: 3 карточки |
| Общество | [Ada Lovelace Institute](https://www.adalovelaceinstitute.org/) | HTML: 3 карточки |
| Общество | [OECD AI Policy Observatory](https://oecd.ai/en/wonk) | HTML: 3 карточки |
| Общество | [EU AI Act official](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) | HTML: 3 карточки |
| Общество | [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) | HTTP 503 |
| Общество | [Stanford HAI Policy](https://hai.stanford.edu/policy) | Сеть/таймаут |
| Общество | [Center for AI Safety](https://www.safe.ai/) | HTML: 2 карточки |
| Общество | [METR](https://metr.org/) | HTML: 3 карточки |
| Общество | [AI Incident Database](https://incidentdatabase.ai/) | Сеть/таймаут |
| Общество | [Partnership on AI](https://partnershiponai.org/) | Автоматически карточки не найдены |
| Общество | [Future of Life Institute](https://futureoflife.org/) | HTML: 3 карточки |
| Общество | [The Gradient](https://thegradient.pub/) | RSS: 3 карточки |
| Общество | [Noema Magazine](https://www.noemamag.com/) | RSS: 3 карточки |
| Общество | [Aeon](https://aeon.co/) | Сеть/таймаут |
| Общество | [MIT Technology Review — AI](https://www.technologyreview.com/topic/artificial-intelligence/) | Автоматически карточки не найдены |
| Общество | [Nature Machine Intelligence](https://www.nature.com/natmachintell/) | Автоматически карточки не найдены |
| Авторы | [Simon Willison](https://simonwillison.net/atom/entries/) | RSS: 3 карточки |
| Авторы | [Ethan Mollick](https://www.oneusefulthing.org/) | RSS: 3 карточки |
| Авторы | [Andrej Karpathy](https://karpathy.ai/) | HTML: 3 карточки; текст частично |
| Авторы | [Andrew Ng](https://www.andrewng.org/) | Автоматически карточки не найдены |
| Авторы | [Lilian Weng](https://lilianweng.github.io/) | RSS: 3 карточки |
| Авторы | [Chip Huyen](https://huyenchip.com/) | RSS: 3 карточки |
| Авторы | [Sebastian Raschka](https://sebastianraschka.com/) | RSS: 3 карточки |
| Авторы | [Gary Marcus](https://garymarcus.substack.com/) | RSS: 3 карточки |
| Авторы | [Yoshua Bengio](https://yoshuabengio.org/) | HTML: 3 карточки; текст частично |
| Авторы | [Geoffrey Hinton](https://www.cs.toronto.edu/~hinton/) | Доступен для чтения |
| Авторы | [Yann LeCun](https://yann.lecun.com/) | Сеть/таймаут |
| Авторы | [Richard Sutton](http://incompleteideas.net/) | Доступен для чтения |
| Авторы | [Eliezer Yudkowsky](https://www.lesswrong.com/users/elizeryudkowsky) | HTTP 404 |
| Авторы | [Scott Alexander](https://www.astralcodexten.com/) | RSS: 3 карточки |
| Авторы | [Zvi Mowshowitz](https://thezvi.substack.com/) | Лента больше 2 МиБ |
| Авторы | [Jürgen Schmidhuber](https://people.idsia.ch/~juergen/) | Доступен для чтения |
| Русскоязычные | [Хабр — Искусственный интеллект](https://habr.com/ru/hubs/artificial_intelligence/) | RSS: 3 карточки |
| Русскоязычные | [Хабр — Машинное обучение](https://habr.com/ru/hubs/machine_learning/) | RSS: 3 карточки |
| Русскоязычные | [Tproger](https://tproger.ru/) | RSS: 3 карточки |
| Русскоязычные | [Код Дурова](https://kod.ru/) | RSS: 3 карточки |
| Русскоязычные | [N+1](https://nplus1.ru/) | robots.txt: HTTP 403 |
| Русскоязычные | [ТАСС — Наука](https://nauka.tass.ru/) | robots.txt: HTTP 403 |
| Русскоязычные | [CNews — Искусственный интеллект](https://ai.cnews.ru/) | RSS: 3 карточки |
| Русскоязычные | [ComNews](https://www.comnews.ru/) | HTML: 3 карточки |
| Русскоязычные | [РБК Тренды](https://trends.rbc.ru/) | HTML: 3 карточки |
| Русскоязычные | [Forbes Russia](https://www.forbes.ru/) | HTML с селекторами: 3 карточки (см. ниже) |
| Русскоязычные | [ПостНаука](https://postnauka.org/) | HTML: 3 карточки |
| Русскоязычные | [Горький](https://gorky.media/) | HTML: 3 карточки |
| Русскоязычные | [Сбер AI](https://developers.sber.ru/) | Автоматически карточки не найдены |
| Русскоязычные | [Yandex Research](https://research.yandex.com/) | HTML: 3 карточки |
| Русскоязычные | [Т-Банк AI Research](https://research.tbank.ru/) | DNS: адрес не найден |
| API и инструменты | [Hacker News Algolia Search](https://hn.algolia.com/api) | Доступен; API-адаптер отсутствует |
| API и инструменты | [arXiv API](https://info.arxiv.org/help/api/) | Доступен; API-адаптер отсутствует |
| API и инструменты | [arXiv RSS](https://rss.arxiv.org/rss/cs.AI) | RSS: 3 карточки |
| API и инструменты | [GitHub REST API](https://docs.github.com/en/rest/releases/releases) | Доступен; API-адаптер отсутствует |
| API и инструменты | [Crossref REST API](https://api.crossref.org/) | Доступен; API-адаптер отсутствует |
| API и инструменты | [OpenAlex API](https://docs.openalex.org/) | Доступен; API-адаптер отсутствует |
| API и инструменты | [Semantic Scholar API](https://api.semanticscholar.org/api-docs/) | Доступен; API-адаптер отсутствует |
| API и инструменты | [GDELT](https://www.gdeltproject.org/) | Доступен; API-адаптер отсутствует |
| API и инструменты | [SearXNG (self-hosted)](https://docs.searxng.org/) | Доступен; API-адаптер отсутствует |
| API и инструменты | [HN RSS](https://hnrss.org/) | Доступен для чтения |

</details>

### Проверенная настройка Forbes

Для `https://www.forbes.ru/` выбрать **HTML**, затем заполнить:

| Поле | Значение |
|---|---|
| Элементы списка | `main a[href]:has(p > span):not([href^="/profile/"]):not([href^="/person/"])` |
| Заголовок | `p > span` |
| Ссылка | `:scope` |

Остальные селекторы оставить пустыми. Получены пять реальных заголовков и
три карточки с текстом без предупреждений; профили авторов исключены.
После изменения вёрстки сайта селекторы нужно перепроверить.

Проверки кода: **461 backend passed**, без failed/skipped, два прежних
предупреждения testcontainers; **65 профильных frontend passed**, TypeScript
и ESLint данных каталога passed. Scheduler перезапущен и healthy. Разметка
интерфейса в этой правке не менялась; доступность проверена существующими
тестами форм/страниц, ручная приёмка не выполнялась. Аудит не создавал
активные источники и не вызывал LLM.

Артефакты в `%TEMP%/bks-news-source-audit-20261008/`: `baseline.json`,
`final.json` (полный повторный проход), `oecd.json` (уточнённый адрес),
`verified.json` (последний результат каждого из 106 URL),
`forbes-configured.json` и сетевые диагностики. В `verified.json` есть время
каждого результата и hash каталога. Логи тестов:
`%TEMP%/bks-news-source-audit-{backend,frontend}-tests.log`.

## Подтверждённая приёмка, 08.10.2026

- Backend: **388 passed**, без failed/skipped; два предупреждения
  testcontainers об устаревшем API. Проверены реальные PostgreSQL-транзакции,
  дедупликация, два scheduler, lease/recovery, отмена, отсутствие ключа,
  авторизация/Origin, RSS/304, HTML, SSRF/DNS/redirect/robots и валидация LLM.
- Frontend: **189 passed**, TypeScript, ESLint и production build — passed.
- Миграция `0004`: upgrade, downgrade/upgrade и `alembic check` — passed.
  Dev и production Compose подняты; backend и отдельный scheduler healthy.
  Production-образы собраны, через локальный HTTPS проверены шесть страниц,
  защищённое API, Secure-сессия и обработка задания production-воркером.
- Живые RSS/Atom Simon Willison и Hugging Face прошли предпросмотр.
  Браузерный сценарий Simon Willison → сохранение источника → сбор → Qwen →
  решение → повторный сбор/анализ — passed. Проверены отсутствие дублей,
  сохранение решения, короткие аннотации и история разных версий запроса.
- Доступность: Chrome, один main/H1, клавиатура, skip-link, видимый фокус,
  две темы, 1280/320 px, forced-colors, увеличение текста до 200%;
  **22 axe-прогона, 0 нарушений**. Для основной кнопки явно заданы
  ButtonFace/ButtonText; читаемость подписи и фокус повторно проверены
  в production при forced-colors. Скриншоты просмотрены. Native browser
  zoom и NVDA/VoiceOver/TalkBack вручную **не проверены**; полного
  подтверждения WCAG одни автоматические проверки не дают.
- `pip-audit`: известных уязвимостей в зависимостях backend не найдено.

После переноса полного каталога: **62 профильных теста passed** (данные,
фильтры, формы и защита страниц), TypeScript, ESLint и production build —
passed. В Chrome с изолированной тестовой сессией и read-only API-заглушкой
прошли **10 проверок**, включая переход из списка источников, все 98 строк,
поиск, фильтры, клавиатуру, раскрытие адресов и заполнение формы с обязательной
проверкой перед сохранением. Светлая/тёмная темы на 1280/320 px:
**4 axe-прогона, 0 нарушений**, горизонтального переполнения нет; скриншоты
просмотрены. Этот проход проверял интерфейс; отдельный живой аудит всех
адресов описан выше. Массовое подключение источников не выполнялось. Артефакты:
`%TEMP%/bks-news-catalogue-{tests,lint,build}.log`,
`%TEMP%/bks-news-20261008/news-browser-catalogue.json` и
`news-catalogue-*.png` в том же каталоге.

Локальные артефакты: `%TEMP%/bks-news-20261008/` (браузер, скриншоты,
HTTPS), `%TEMP%/bks-news-backend-final.log`,
`%TEMP%/bks-news-frontend-full-after-focus.log`,
`%TEMP%/bks-news-production-build-final.log`,
`%TEMP%/bks-news-production-frontend-forced.log` и
`%TEMP%/bks-news-python-audit.json`. Первичные браузерные отчёты сохраняют
сбои проверочного скрипта; выход и увеличение текста подтверждены отдельно
в `news-browser-resize-logout.json`, исправление высокой контрастности —
в `news-browser-forced-final.json`. Публичное развёртывание не выполнялось;
изолированный production-стенд остановлен после проверки, локальный
просмотр и dev scheduler оставлены запущенными. Секреты в артефакты
не записываются.
