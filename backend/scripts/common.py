"""Shared helpers for the content generator scripts (new_article/new_note/new_project)."""

import sys
import re
from datetime import date
from pathlib import Path

CONTENT_ROOT = Path(__file__).resolve().parent.parent / "content"

ARTICLE_TEMPLATE = """---
title: "{title}"
excerpt: "Краткое описание статьи."
category: development
published_at: {today}
cover_image: "/images/articles/{slug}.webp"
tags: []
draft: true
---

## Введение

Текст статьи.
"""

NOTE_TEMPLATE = """---
title: "{title}"
published_at: {today}
tags: []
draft: true
---

Текст заметки.
"""

PROJECT_TEMPLATE = """---
title: "{title}"
excerpt: "Краткое описание проекта."
cover_image: "/images/projects/{slug}.webp"
tags: ["project"]
status: active
featured: false
order: 100
draft: true
---

## Проблема

Описание проекта.
"""

TEMPLATES = {
    "article": ("articles", ARTICLE_TEMPLATE),
    "note": ("notes", NOTE_TEMPLATE),
    "project": ("projects", PROJECT_TEMPLATE),
}


def create_content_file(content_type: str, slug: str) -> Path:
    """Create a new Markdown file with a valid frontmatter template.

    Args:
        content_type: article | note | project.
        slug: File slug (lowercase latin letters, digits, hyphens; at most 200 characters).

    Returns:
        Path of the created file.

    Raises:
        SystemExit: On invalid slug or when the file already exists.
    """
    directory, template = TEMPLATES[content_type]
    if len(slug) > 200 or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is None:
        sys.exit(f"Invalid slug: {slug!r} (lowercase latin letters, digits, hyphens; max 200 characters)")
    target = CONTENT_ROOT / directory / f"{slug}.md"
    if target.exists():
        sys.exit(f"File already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    title = slug.replace("-", " ").capitalize()
    target.write_text(
        template.format(title=title, slug=slug, today=date.today().isoformat()),
        encoding="utf-8",
    )
    return target
