# BKS Lab — формат контента

**Версия:** 0.3 (по результатам ревью: reading_time, маппинг статусов проекции)

Контент (статьи блога, заметки, проекты) хранится в репозитории как
Markdown-файлы с YAML-frontmatter в `backend/content/`. Бэкенд парсит их
repository-слоем, отдаёт через API (`docs/api_contract.md`) и синхронизирует
проекцию метаданных в PostgreSQL (`content_items`, см. `docs/architecture.md`
§3) — для админки и будущего анализа агентами.

## Структура каталогов

```text
backend/content/
  articles/
    1c-async.md           # имя файла = slug
    ai-developer.md
  notes/
    small-team-deploys.md
  projects/
    work-for-everyone.md
    service-desk.md
    legal-rag.md
```

Slug: строчные латинские буквы и цифры, разделённые одиночными дефисами;
длина — 1–200 символов, без дефиса в начале или конце. Уникален внутри
типа контента. У статей и проектов совпадает с URL на сайте. Файл с
невалидным slug исключается из API и проекции; генераторы такой slug
не принимают.

## Статья (`articles/<slug>.md`)

```markdown
---
title: "Как мы вынесли синхронизации 1С в отдельный асинхронный контур"
excerpt: "Аннотация 1–3 предложения для карточек и meta description."
category: development
published_at: 2026-02-10
cover_image: "/images/articles/1c-async.webp"
tags: ["1C", "async", "architecture"]
reading_time: 8
seo_title: "… (опционально, default = title)"
seo_description: "… (опционально, default = excerpt)"
og_image: "/og/articles/1c-async.jpg (опционально, default = /og/bks-lab-default.jpg)"
draft: false
---

Текст статьи в Markdown (GFM: таблицы, сноски, code blocks).
```

Обязательные поля: `title`, `excerpt`, `category`, `published_at`,
`cover_image`.

- `reading_time` — **опциональный override**; по умолчанию вычисляется из
  `word_count` (200 слов/мин, минимум 1) — единая механика для всех типов.
- `draft: true` — исключает статью из публичного API и поиска; в проекцию
  синхронизируется со `status=draft` (видна в админке).
- `category` — один из: `development`, `ai`, `management`, `thoughts`,
  `accessibility` (ТЗ §11). Заголовки категорий зашиты на бэкенде, не в файлах.

## Заметка (`notes/<slug>.md`)

«Заметка на полях» — короткий материал (1–3 абзаца, ориентир до 500 слов).
Отдельной страницы в v1 нет: публикуется в ленте `/notes` с якорем
`#note-<slug>`; последние заметки выводятся на главной и в сайдбаре блога.

```markdown
---
title: "Почему маленькие команды деплоят чаще"
published_at: 2026-02-12
tags: ["management", "deploy"]
related: "1c-async"
draft: false
---

Текст заметки в Markdown — короткий, заголовки в теле не используются.
```

Обязательные поля: `title`, `published_at`.

- `tags` — опционально, свободный список (категорий у заметок нет).
- `related` — опционально, slug статьи: в ленте заметка показывает ссылку
  «по теме: …» на связанную статью. Битая ссылка не блокирует публикацию
  (логируется, `related_article` в API = null).
- Обложки и категории нет. `excerpt` = первый абзац (вычисляется),
  `reading_time` = из `word_count` (минимум 1).

## Проект (`projects/<slug>.md`)

```markdown
---
title: "Работа для всех"
excerpt: "Платформа с вакансиями для людей с инвалидностью и AI-помощником."
cover_image: "/images/projects/work-for-everyone.webp"
tags: ["FastAPI", "Next.js", "PostgreSQL", "AI"]
status: active
featured: true
order: 1
seo_title: "… (опционально)"
seo_description: "… (опционально)"
draft: false
---

Описание проекта в Markdown: проблема, решение, архитектура, результаты.
```

Обязательные поля: `title`, `excerpt`, `cover_image`, `tags`, `status`,
`featured`, `order`.

- `status`: `active | archived` (`archived` — только у проектов).
- `featured: true` + `order` — выбор и порядок проектов на главной (ТЗ §10).
- Стартовые проекты (ТЗ §10): `work-for-everyone`, `service-desk`, `legal-rag`.

## Правила Markdown-тела

- Заголовки внутри статьи/проекта начинаются с `##` (H1 — `title` из
  frontmatter, рендерится страницей; иерархия заголовков — требование ТЗ §14).
  В заметках заголовки не используются.
- Изображения внутри текста — с осмысленным alt; декоративные — пустой alt.
- Пути к изображениям — абсолютные от web-root (`/images/...`), файлы лежат в
  `frontend/public/` по слотам дизайн-ТЗ §7.
- GFM: таблицы, code fences с указанием языка, сноски. Raw HTML в Markdown
  запрещён (санитизация всё равно вырежет).

## Проекция в БД

Механика синхронизации (триггер, single-flight, транзакция) — в
`docs/architecture.md` §3 «Механика синхронизации контента». Маппинг в
`content_items`:

| Источник (frontmatter)          | `content_items.status` | Публичный API |
| ------------------------------- | ---------------------- | ------------- |
| обычный файл                    | `active`               | да            |
| `draft: true`                   | `draft`                | нет           |
| проект `status: archived`       | `archived`             | да (помечен)  |

- Файл, не прошедший валидацию, исключается из выдачи и **удаляется** из
  кэша и `content_items` (в транзакции рескана); ошибка логируется.
- Nullable-поля проекции: `category` (только статьи), `reading_time`
  (статьи/заметки).
- Это read-model: правка БД напрямую не влияет на сайт и будет затёрта
  следующей синхронизацией.

## Валидация

Repository при рескане валидирует frontmatter Pydantic-схемой. Тесты бэкенда
включают фикстуру с валидным и невалидным frontmatter.
