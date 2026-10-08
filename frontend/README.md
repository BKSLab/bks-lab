# BKS Lab — frontend

Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS 4.

Запуск и проверки описаны в корневом [README](../README.md).

## Структура

- `src/app/(public)/` — публичная часть (общий layout: header, footer,
  SkipLink, PageViewTracker, FocusManager).
- `src/app/(admin)/admin/` — защищённая панель владельца; `news/` — редакционный центр.
- `src/components/{layout,navigation,tracking,ui,admin}/` — компоненты.
- `src/lib/api/` — типизированный клиент публичного API (`docs/api_contract.md`).
- `src/lib/admin-api/`, `src/lib/news-api/` — серверные запросы, проверка сессии
  и клиентские мутации закрытого API.
- `src/styles/tokens.css` — светлая/тёмная палитры и системные цвета для forced-colors.
- `public/brand/`, `public/images/`, `public/og/` — готовые логотипы,
  фирменные изображения и обложки. Исторический `scripts/generate_placeholders.py`
  не запускать поверх этих файлов: он заменяет их заглушками.

Публикации редактируются в `backend/content/` через git. Админка показывает
их read-only; редактирование источников и решений News Analyzer касается
отдельных данных PostgreSQL. Подробности — в [инструкции редакционного центра](../docs/news_analyzer.md).
