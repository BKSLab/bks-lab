"""Content generators must create valid, safely named draft files."""

import pytest

from scripts import common
from src.schemas.frontmatter import ArticleFrontmatter, NoteFrontmatter, ProjectFrontmatter
from src.utils.markdown import is_valid_slug, parse_frontmatter


@pytest.mark.parametrize("content_type, model", [
    ("article", ArticleFrontmatter),
    ("note", NoteFrontmatter),
    ("project", ProjectFrontmatter),
])
@pytest.mark.parametrize("slug", ["new-example-2", pytest.param("a" * 200, id="max-length")])
def test_generated_content_has_valid_draft_frontmatter(content_type, model, tmp_path, monkeypatch, slug):
    monkeypatch.setattr(common, "CONTENT_ROOT", tmp_path)

    path = common.create_content_file(content_type, slug)
    metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    frontmatter = model.model_validate(metadata)

    assert frontmatter.draft is True
    assert frontmatter.title
    assert body
    assert is_valid_slug(path.stem)


@pytest.mark.parametrize("slug", [
    "", "русский", "a--b", "-abc", "abc-", "abc\n", "../escape", "a_b", "abc١",
    pytest.param("a" * 201, id="over-max-length"),
])
def test_generator_rejects_slugs_rejected_by_content_parser(slug, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "CONTENT_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="Invalid slug"):
        common.create_content_file("article", slug)

    assert not is_valid_slug(slug)
    assert list(tmp_path.iterdir()) == []
