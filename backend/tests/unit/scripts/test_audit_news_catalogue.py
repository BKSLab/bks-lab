"""Ensure catalogue audits cover all addresses without mixing API access with discovery."""

import pytest

from scripts.audit_news_catalogue import audit_targets, read_catalogue


@pytest.mark.parametrize("prefix,suffix", [
    ("", ""),
    ("\ufeffexport const sourceCatalogue: SourceCatalogueEntry[] = ", ";\n"),
])
def test_reads_json_and_typescript_catalogues(prefix: str, suffix: str) -> None:
    entries = read_catalogue(prefix + '[{"id":"source","url":"https://example.org/"}]' + suffix)
    assert entries == [{"id": "source", "url": "https://example.org/"}]


def test_covers_homepages_feeds_extras_and_duplicate_rows() -> None:
    entries = [
        {"id": "author", "url": "https://example.org/", "feedUrl": "https://example.org/feed",
         "mode": "rss", "extraUrls": ["https://example.org/all"]},
        {"id": "engineering", "url": "https://example.org/", "feedUrl": "https://example.org/feed",
         "mode": "rss", "extraUrls": []},
        {"id": "api", "url": "https://api.example.org/", "mode": "api",
         "extraUrls": ["https://api.example.org/search"]},
        {"id": "archive", "url": "https://archive.example.org/", "mode": "read", "extraUrls": []},
    ]
    targets = {row["url"]: row for row in audit_targets(entries)}
    assert len(targets) == 6
    assert targets["https://example.org/feed"]["primary_ids"] == ["author", "engineering"]
    assert targets["https://example.org/feed"]["kind"] == "rss"
    assert targets["https://example.org/"]["primary_ids"] == []
    assert targets["https://example.org/"]["kind"] is None
    assert targets["https://example.org/all"]["discover"] is True
    assert targets["https://api.example.org/"]["discover"] is False
    assert targets["https://api.example.org/search"]["discover"] is False
    assert targets["https://archive.example.org/"]["discover"] is False
