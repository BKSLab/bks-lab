# BKS Lab — редактор контента в админке

**Версия:** 1.0 (реализовано)
**Статус:** этапы 1–5 (§9) реализованы; backend pytest и frontend vitest
зелёные. Ручная интеграционная приёмка по §10 не проводилась.

## 1. Цель и контекст

В админке (`/admin`) реализован редактор статей, заметок и проектов:
создание и правка материалов, загрузка изображений, вставка рекламных блоков,
история версий (ревизии).

Редактор заменил прежнее решение проекта «Markdown-файлы в git — источник истины,
админка read-only» (AGENTS.md, `docs/content_format.md`, `docs/architecture.md`
§3). Новое решение: **источник истины — PostgreSQL**, Markdown остаётся
форматом разметки тела материала. Документ описывает реализованное состояние;
упомянутые документы и AGENTS.md согласованы с этим решением.

Текущее состояние:

- Админская сессия, Origin-защита и паттерн мутаций уже отработаны в
  News Analyzer (`backend/src/api/news.py`, `frontend/src/lib/news-api/client.ts`).
- Публикации создаются и редактируются только в админке
  (`frontend/src/app/(admin)/admin/content/`).
- Рендер-пайплайн Markdown → HTML на бэкенде (`backend/src/utils/markdown.py`),
  санитизация на фронте (`frontend/src/lib/sanitize.ts`).
- Таблица `content_items` — источник истины: поля публикации, Markdown,
  HTML и производные значения. История сохраняется в `content_revisions`.
- Инвалидация кеша фронтенда — webhook `POST /api/revalidate` с Bearer-секретом
  (`frontend/src/app/api/revalidate/route.ts`), вызывается backend после
  мутации контента. Пересборка frontend для публикации не требуется.

## 2. Принятые решения

1. **Хранение в PostgreSQL.** `content_items` становится основным хранилищем
   материалов (полный набор полей + исходный Markdown + отрендеренный HTML).
2. **Markdown остаётся форматом тела.** Меняется место хранения, не разметка.
   Пайплайн `markdown-it-py` → HTML → DOMPurify сохраняется без изменений.
3. **Ревизии.** Каждое сохранение материала пишет снапшот в
   `content_revisions`; доступны просмотр списка версий и откат.
4. **Git перестаёт быть хранилищем контента.** Существующие файлы
   `backend/content/` импортируются в БД одноразово и далее не читаются
   приложением. История контента — ревизии в БД, резервная копия —
   `scripts/backup-database.sh`.
5. **Изображения загружаются через админку** в отдельное файловое хранилище
   (Docker volume), отдаются по `/uploads/...`. Дизайнерские ассеты
   `frontend/public/images/` не затрагиваются.
6. **Рекламные блоки внутри текста** вставляются маркером в Markdown и
   рендерятся через существующий `AdSlot` (см. §7, включая конфликт с
   текущим правилом проекта).
7. **Публикация = сохранение в БД + вызов revalidate-webhook фронтенда.**
   `scripts/publish-content.sh` для контента больше не нужен.

## 3. Модель данных

### 3.1. `content_items` — расширение до полного хранилища

Существующие колонки сохраняются (`id`, `type`, `slug`, `title`, `category`,
`tags`, `published_at`, `reading_time`, `status`, `word_count`,
`content_text`). Новые колонки:

| Колонка            | Тип             | Назначение |
| ------------------ | --------------- | ---------- |
| `excerpt`          | Text, null      | Аннотация (статьи/проекты); у заметок вычисляется из первого абзаца |
| `cover_image`      | String(500), null | Путь обложки (`/images/...` или `/uploads/...`) |
| `seo_title`        | Text, null      | SEO-override заголовка |
| `seo_description`  | Text, null      | SEO-override описания |
| `og_image`         | String(500), null | OG-изображение |
| `related_slug`     | String(200), null | Заметки: slug связанной статьи |
| `featured`         | Boolean         | Проекты: показ на главной |
| `sort_order`       | Integer, null   | Проекты: порядок на главной |
| `content_markdown` | Text            | Исходный Markdown тела |
| `content_html`     | Text            | Отрендеренный HTML (рендер при сохранении, кеш) |
| `created_at`       | DateTime(tz)    | Создание материала |
| `updated_at`       | DateTime(tz)    | Последнее сохранение |

- `status`: `draft | active | archived` (archived — только проекты), семантика
  как в текущем маппинге (`docs/content_format.md` §Проекция).
- `content_hash` и `synced_at` удаляются — это артефакты файловой
  синхронизации.
- Уникальность `(type, slug)` сохраняется; валидация slug — по правилам
  `docs/content_format.md` (схема переносится на уровень API).
- Один админ — поля автора не вводим.

### 3.2. `content_revisions` — история версий

| Колонка        | Тип           | Назначение |
| -------------- | ------------- | ---------- |
| `id`           | PK            | |
| `item_id`      | FK → content_items.id, ON DELETE CASCADE | |
| `revision_no`  | Integer       | Номер версии внутри материала, начиная с 1 |
| `snapshot`     | JSONB         | Все редактируемые поля, включая `content_markdown` |
| `word_count`   | Integer       | Для быстрого отображения в списке версий |
| `created_at`   | DateTime(tz)  | Момент сохранения |

- Снапшот пишется на **каждое** успешное сохранение (и на импорт, ревизия 1).
- Откат = копирование снапшота выбранной ревизии в `content_items` + новая
  ревизия с этим же содержимым (история не перезаписывается).
- Уникальный индекс `(item_id, revision_no)`; индекс по `item_id` для списка.

### 3.3. `media_files` — загруженные изображения

| Колонка        | Тип           | Назначение |
| -------------- | ------------- | ---------- |
| `id`           | PK            | |
| `path`         | String(500), unique | Публичный путь `/uploads/<sub>/<file>.webp` |
| `original_name`| String(255)   | Имя исходного файла |
| `mime`         | String(50)    | Итоговый MIME (`image/webp`) |
| `size_bytes`   | Integer       | |
| `width`/`height` | Integer, null | Для alt/превью и валидации |
| `created_at`   | DateTime(tz)  | |

Файлы — в Docker volume `uploads`, подкаталоги по типу контента
(`articles/`, `notes/`, `projects/`, `covers/`). Правила загрузки:

- Принимаются jpeg/png/webp; лимит размера исходника (предложение: 5 МБ).
- Конвертация в webp через Pillow, даунскейл до максимальной ширины
  (предложение: 1920px), имя файла — slugified + короткий суффикс.
- Dev: раздаёт backend (StaticFiles). Prod: тот же volume монтируется в
  nginx, локейшен `/uploads/` с кеш-заголовками — backend из раздачи уходит.

## 4. Backend

Слои и паттерны — по `docs/FASTAPI_PATTERNS.md`: `api → services →
repositories → PostgreSQL`, все эндпоинты только под `/api/admin`,
за `require_admin` + `check_admin_origin`, ответы no-store.

### 4.1. Репозитории

- `ContentItemRepository` — переписывается с sync-механики на полный CRUD:
  create, update, get, get_by_slug, список с фильтрами/пагинацией (текущий
  `get_page` сохраняется), delete (с каскадом ревизий).
- `ContentRevisionRepository` — create, list по item, get, last revision_no.
- `MediaFileRepository` — create, list, get, delete (с удалением файла).
- `MarkdownContentRepository` и файловый rescan (`ensure_fresh`, TTL,
  `_sync_projection`) — **удаляются** после миграции; парсер frontmatter
  переезжает в импортёр (§6).

### 4.2. Сервисы

- `ContentAdminService` — CRUD + смена статуса + откат ревизии. При
  сохранении: валидация Pydantic-схемой (поля по типу контента — обязательные
  поля как в `docs/content_format.md`), рендер `content_markdown` →
  `content_html` существующим `markdown.py`, пересчёт `word_count`,
  `content_text`, `reading_time`, запись ревизии — одной транзакцией.
- `ContentRenderService` (или функция в утилитах) — единая точка рендера,
  используется и при сохранении, и в превью.
- `MediaService` — приём upload, валидация, конвертация Pillow, запись
  файла и строки `media_files`.
- `RevalidationClient` — после мутации вызывает
  `POST {FRONTEND_INTERNAL_URL}/api/revalidate` с
  `Authorization: Bearer {REVALIDATE_SECRET}` (secret добавляется в env
  backend; failure логируется и **не валит** сохранение — кеш сам истечёт
  по `revalidate = 300`).
- Публичные сервисы (`articles.py`, `notes.py`, `projects.py`,
  `categories.py`, `admin_content.py`) переключаются с
  `MarkdownContentRepository` на `ContentItemRepository`; выдача
  фильтруется по `status` как сейчас (draft скрыт, archived помечен).
  `content_html` отдаётся из БД, повторный рендер на чтении не нужен.

### 4.3. Admin API (новые эндпоинты, роутер `/admin/content`)

| Метод | Путь | Назначение |
| ----- | ---- | ---------- |
| GET | `/admin/content` | список (уже есть, остаётся) |
| GET | `/admin/content/{id}` | детали **+ `content_markdown`** для редактора |
| POST | `/admin/content` | создать материал (по умолчанию `draft`) |
| PATCH | `/admin/content/{id}` | сохранить правки (пишет ревизию) |
| DELETE | `/admin/content/{id}` | удалить материал (с подтверждением на фронте) |
| POST | `/admin/content/{id}/status` | смена статуса draft/active/archived |
| GET | `/admin/content/{id}/revisions` | список версий |
| GET | `/admin/content/{id}/revisions/{no}` | снапшот версии |
| POST | `/admin/content/{id}/revisions/{no}/restore` | откат |
| POST | `/admin/content/preview` | рендер Markdown → sanitized HTML для живого превью |
| POST | `/admin/content/images` | загрузка изображения (multipart) |
| GET | `/admin/content/images` | список загруженных (для диалога вставки) |

Контракт детализируется в `docs/api_contract.md` при реализации.

## 5. Frontend: редактор

Новые маршруты в `(admin)`:

- `/admin/content/new?type=article|note|project` — создание.
- `/admin/content/[id]/edit` — правка: форма метаданных (по типу контента),
  редактор тела, панель статуса, вкладка «Версии».

Компоненты (`frontend/src/components/admin/editor/`):

- `MarkdownEditor` — поле ввода с тулбаром: жирный, курсив, H2/H3, цитата,
  ссылка, списки, код, вставка изображения, вставка рекламного блока.
  Основа — CodeMirror 6 (`@uiw/react-codemirror`): подсветка,
  нормальная клавиатурная навигация. Зависимость согласована владельцем
  (лицензия MIT).
- `EditorPreview` — живое превью: дебаунс → `POST /admin/content/preview` →
  вывод через существующий `ContentHtml` (тот же sanitize + `prose-content`,
  превью визуально совпадает с публикацией).
- `ImageInsertDialog` — загрузка файла или выбор из уже загруженных;
  вставляет `![alt](/uploads/...)` в позицию курсора. Поле alt обязательно
  для не-декоративных изображений (подсказка в UI).
- `RevisionList` — список версий (дата, word_count), просмотр снапшота,
  кнопка «Откатить» с подтверждением.
- Список `/admin/content` и карточка получают кнопки «Создать», «Править»;
  плашки «тексты редактируются в Markdown-файлах» убираются.

Доступность (дизайн-ТЗ §14, §22): редактор — обычный текстовый контрол с
label, тулбар — кнопки с `aria-label` и фокус-стилями, диалоги — с focus
trap и закрытием по Esc, превью не уводит фокус.

## 6. Первый production-запуск

Production разворачивается с пустой БД. Локальная БД, её публикации и
загруженные изображения не переносятся. Все статьи, заметки и проекты
создаются только в редакторе `/admin/content`.

Файлы `backend/content/` остаются историческим архивом и исключены из
Docker-образа; приложение их не читает. Исторический скрипт
`backend/scripts/import_content_to_db.py` сохранён для локальных фикстур
и проверок прежнего импорта, но при развёртывании не запускается.

## 7. Рекламные блоки внутри текста

**Конфликт с текущим правилом:** AGENTS.md сейчас запрещает РСЯ «внутри
текста статей». Владелец вводит возможность вставки рекламы в теле статьи —
правило пересматривается, при реализации AGENTS.md обновляется.

Механика:

- Маркер в Markdown — строка, содержащая только `::ad`. Плагин markdown-it
  (или пост-обработка HTML) превращает её в плейсхолдер
  `<div data-ad-slot="article-inline"></div>`.
- Фронтенд в `ContentHtml` расщепляет HTML по плейсхолдерам и между частями
  рендерит `AdSlot` (фиксированная высота, `<aside aria-label="Реклама">` —
  требования сохраняются).
- Ограничения (валидируются сервером при сохранении): маркеры только в
  статьях, не более 2 на материал, не первым и не последним абзацем.
  Заметки и проекты — без внутритекстовой рекламы.
- На главной рекламы по-прежнему нет; в dev блоки скрыты флагом, как сейчас.

## 8. Что удаляется и обновляется

- `MarkdownContentRepository`, файловый rescan, колонки `content_hash` /
  `synced_at`, `scripts/publish-content.sh` (часть контента; если скрипт
  используется ещё для чего-то — пересмотреть).
- Документы при реализации: `docs/content_format.md` (переписывается: формат
  полей остаётся, хранилище — БД), `docs/architecture.md` §3 (новая модель
  контента), `docs/api_contract.md` (новые эндпоинты), AGENTS.md (правила
  read-only админки и запрета рекламы в тексте), README (команды).
- `.env.production.example`, `docker-compose*.yml`: `REVALIDATE_SECRET` и
  `FRONTEND_INTERNAL_URL` для backend, volume `uploads`, локейшен nginx.

## 9. Этапы реализации

1. **Хранилище в БД.** Миграция Alembic (новые колонки + `content_revisions`),
   CRUD-репозиторий, скрипт импорта, переключение публичного API на БД,
   удаление файловой синхронизации. DoD: сайт полностью работает на данных
   из БД после импорта, pytest backend зелёный, фронтенд не менялся.
2. **Admin CRUD API + ревизии.** Эндпоинты §4.3 (кроме preview/images),
   запись ревизий, revalidate-webhook после мутаций. DoD: pytest на CRUD,
   статусы, откат, уникальность slug, права (без сессии/Origin — 401/403).
3. **Редактор.** Маршруты и компоненты §5, превью через
   `/admin/content/preview`, вкладка версий с откатом. DoD: vitest на
   компоненты редактора, проход чек-листа доступности §22 на страницах
   редактора, ручная приёмка: создание → правка → публикация → откат.
4. **Изображения.** `media_files`, upload-эндпоинт, MediaService (Pillow),
   volume + раздача (dev/prod), диалог вставки. DoD: pytest на валидацию и
   конвертацию, картинка отображается в превью и на опубликованной странице.
5. **Рекламный маркер + документация.** Плейсхолдер `::ad`, расщепление в
   `ContentHtml`, серверные лимиты; правка AGENTS.md, `content_format.md`,
   `architecture.md`, `api_contract.md`, README. DoD: тест на лимиты
   маркеров, блок с фиксированной высотой и `aria-label` в DOM статьи.

## 10. Тестирование

- Backend: pytest + httpx — CRUD, ревизии (запись, список, откат), импорт
  (идемпотентность), валидация по типам контента, upload (тип/размер),
  права доступа, что публичная выдача фильтрует draft.
- Frontend: Vitest + Testing Library — тулбар вставляет разметку, превью
  дебаунсится, диалог изображений, список версий.
- A11y: чек-лист дизайн-ТЗ §22 на новых страницах админки; отчёт, что
  проверено.
- Ручная интеграционная приёмка на docker-compose: полный цикл
  «создал → отредактировал → опубликовал → откатил → удалил».

## 11. Риски и открытые вопросы

- **Бэкап становится критичным.** Контент теперь только в БД; проверить,
  что `scripts/backup-database.sh` покрывает `content_items`,
  `content_revisions`, `media_files`, и что volume `uploads` включён в
  бэкап файлов (сейчас бэкапит ли он файлы — проверить на этапе 4).
- **Экспорт в Markdown.** Не входит в объём; при желании позже — команда
  выгрузки БД обратно в файлы (поля позволяют восстановить формат 1:1).
- **Конкурентные правки.** Один админ — конфликтов нет; optimistic locking
  (`updated_at` в PATCH) добавляем только если появится второй редактор.
- **Просмотры и статистика** уже ведутся по `content_items.id` — при
  переключении хранилища id материалов сохранить (импорт upsert-ит по
  `(type, slug)` в существующие строки), чтобы статистика не обнулилась.
