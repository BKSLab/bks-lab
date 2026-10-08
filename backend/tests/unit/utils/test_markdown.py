"""Unit tests for the Markdown parsing utilities."""

import pytest

from src.utils.markdown import (
    MarkdownParseError,
    content_hash,
    count_words,
    extract_excerpt,
    extract_plain_text,
    is_valid_slug,
    parse_frontmatter,
    reading_time_minutes,
    render_markdown,
)


def test_parse_frontmatter_splits_meta_and_body() -> None:
    data, body = parse_frontmatter('---\ntitle: "Hi"\ntags: [a]\n---\n\nBody text.\n')

    assert data == {"title": "Hi", "tags": ["a"]}
    assert body == "Body text."


def test_parse_frontmatter_raises_without_delimiters() -> None:
    with pytest.raises(MarkdownParseError):
        parse_frontmatter("no frontmatter here")


def test_parse_frontmatter_raises_on_unclosed_block() -> None:
    with pytest.raises(MarkdownParseError):
        parse_frontmatter("---\ntitle: Hi\n")


def test_parse_frontmatter_wraps_yaml_syntax_error() -> None:
    with pytest.raises(MarkdownParseError, match="invalid YAML"):
        parse_frontmatter("---\ntitle: [\n---\nBody")


@pytest.mark.parametrize("scalar, constructor_error", [
    pytest.param("2026-02-30", ValueError, id="invalid-date"),
    # YAML 1.1 sexagesimal floats can overflow during their construction.
    pytest.param("1:" * 180 + "1.0", OverflowError, id="overflowing-float"),
])
def test_parse_frontmatter_wraps_yaml_constructor_failures(scalar, constructor_error) -> None:
    with pytest.raises(MarkdownParseError, match="invalid YAML") as error:
        parse_frontmatter(f"---\npublished_at: {scalar}\n---\nBody")

    assert isinstance(error.value.__cause__, constructor_error)


def test_render_markdown_supports_gfm_and_escapes_raw_html() -> None:
    html = render_markdown("## Head\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n~~del~~ <b>raw</b>")

    assert "<h2>" in html
    assert "<table>" in html
    assert "<s>" in html
    assert "&lt;b&gt;" in html


def test_extract_plain_text_strips_formatting() -> None:
    text = extract_plain_text("## Title\n\nSome *bold* `code` text.\n\n```python\nx = 1\n```")

    assert "Some bold code text." in text
    assert "x = 1" in text
    assert "Title" not in text or "##" not in text


def test_extract_excerpt_returns_first_paragraph() -> None:
    assert extract_excerpt("First paragraph.\n\nSecond paragraph.") == "First paragraph."


def test_extract_excerpt_joins_soft_line_breaks_with_space() -> None:
    assert extract_excerpt("First line\nsecond line.\n\nOther.") == "First line second line."


def test_count_words_and_reading_time() -> None:
    assert count_words("one two three") == 3
    assert reading_time_minutes(0) == 1
    assert reading_time_minutes(199) == 1
    assert reading_time_minutes(200) == 1
    assert reading_time_minutes(201) == 2
    assert reading_time_minutes(400) == 2


def test_content_hash_is_stable() -> None:
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")


def test_slug_validation() -> None:
    assert is_valid_slug("1c-async")
    assert is_valid_slug("note")
    assert not is_valid_slug("Not-A-Slug")
    assert not is_valid_slug("bad slug")
    assert not is_valid_slug("")
    assert is_valid_slug("a" * 200)
    assert not is_valid_slug("a" * 201)
