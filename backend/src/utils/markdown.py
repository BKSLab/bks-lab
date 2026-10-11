"""Markdown content pipeline: frontmatter parsing, HTML rendering, text stats.

Raw HTML inside Markdown is disabled on purpose (see docs/content_format.md):
it would be stripped by sanitization anyway.
"""

import hashlib
import math
import re
from collections.abc import Iterator
from typing import Any

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

FRONTMATTER_DELIMITER = "---"

_WORDS_PER_MINUTE = 200

_markdown = (
    MarkdownIt("commonmark", {"html": False})
    .enable(["table", "strikethrough"])
    .use(footnote_plugin)
)

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Inline ad marker (docs/content_editor.md §7): a standalone "::ad" line in an
# article body becomes a placeholder the frontend replaces with an AdSlot.
AD_MARKER = "::ad"
AD_PLACEHOLDER = '<div data-ad-slot="article-inline"></div>'
AD_MARKER_MAX = 2

_AD_MARKER_LINE = re.compile(r"^[ \t]*::ad[ \t]*$")
_FENCE_LINE = re.compile(r"^[ \t]*(```|~~~)")


def _content_lines(body: str) -> Iterator[str]:
    """Yield lines outside fenced code blocks (markers in code are literal)."""
    in_fence = False
    for line in body.splitlines():
        if _FENCE_LINE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line


def count_ad_markers(body: str) -> int:
    """Count standalone ::ad marker lines, ignoring fenced code blocks."""
    return sum(1 for line in _content_lines(body) if _AD_MARKER_LINE.match(line))


def ad_marker_error(content_type: str, body: str) -> str | None:
    """Return a validation error message for misplaced ad markers, or None.

    Rules: articles only, at most AD_MARKER_MAX markers, and a marker may not
    be the first or the last block of the body.
    """
    count = count_ad_markers(body)
    if count == 0:
        return None
    if content_type != "article":
        return "Ad markers are allowed in articles only"
    if count > AD_MARKER_MAX:
        return f"At most {AD_MARKER_MAX} ad markers per article"
    blocks = [block.strip() for block in re.split(r"\n[ \t]*\n", body) if block.strip()]
    if blocks and (blocks[0] == AD_MARKER or blocks[-1] == AD_MARKER):
        return "An ad marker may not be the first or last block"
    return None


class MarkdownParseError(Exception):
    """Raised when a Markdown file has no valid frontmatter block."""


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into (frontmatter dict, body).

    Args:
        raw: Full file content, expected to start with a ``---`` block.

    Returns:
        Tuple of the parsed YAML mapping and the Markdown body.

    Raises:
        MarkdownParseError: If frontmatter is missing, malformed, or not a mapping.
    """
    lines = raw.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise MarkdownParseError("frontmatter block not found")
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == FRONTMATTER_DELIMITER
        )
    except StopIteration:
        raise MarkdownParseError("frontmatter block is not closed") from None
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except (yaml.YAMLError, ValueError, OverflowError) as error:
        # PyYAML scalar constructors also expose native datetime/number errors.
        raise MarkdownParseError("invalid YAML frontmatter") from error
    if not isinstance(data, dict):
        raise MarkdownParseError("frontmatter is not a YAML mapping")
    body = "\n".join(lines[end + 1 :]).strip()
    return data, body


def render_markdown(body: str) -> str:
    """Render Markdown body to HTML (GFM: tables, strikethrough, footnotes).

    Standalone ::ad lines become the inline ad placeholder; the frontend
    splits stored HTML on it and mounts an AdSlot between content parts.
    """
    html = _markdown.render(body)
    return html.replace(f"<p>{AD_MARKER}</p>", AD_PLACEHOLDER)


def _collect_inline_text(children: list, break_char: str) -> str:
    """Join inline token children; soft/hard line breaks become break_char."""
    parts: list[str] = []
    for child in children:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(break_char)
    return "".join(parts)


def extract_plain_text(body: str) -> str:
    """Extract human-readable plain text from a Markdown body.

    Inline formatting markers are dropped; fenced code content is kept so the
    projection stays useful for future content analysis.
    """
    parts: list[str] = []
    for token in _markdown.parse(body):
        if token.type == "inline" and token.children:
            parts.append(_collect_inline_text(token.children, "\n"))
        elif token.type == "fence":
            parts.append(token.content)
    return "\n".join(part for part in parts if part.strip())


def extract_excerpt(body: str) -> str:
    """Extract the first paragraph of a Markdown body as plain text."""
    for token in _markdown.parse(body):
        if token.type == "inline" and token.children:
            text = _collect_inline_text(token.children, " ").strip()
            if text:
                return text
    return ""


def count_words(text: str) -> int:
    """Count whitespace-separated words in plain text."""
    return len(text.split())


def reading_time_minutes(word_count: int, words_per_minute: int = _WORDS_PER_MINUTE) -> int:
    """Derive reading time in minutes from word count (minimum 1)."""
    return max(1, math.ceil(word_count / words_per_minute))


def content_hash(raw: str) -> str:
    """Return the SHA-256 hex digest of the raw file content."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_valid_slug(slug: str) -> bool:
    """Check the database limit and lowercase latin letter/digit/hyphen format."""
    return len(slug) <= 200 and bool(_SLUG_PATTERN.fullmatch(slug))
