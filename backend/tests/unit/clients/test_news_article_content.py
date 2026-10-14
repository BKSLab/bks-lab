"""Article layouts observed during the catalogue audit, with synthetic text."""

from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients.news_http import NewsHttpResponse, SafeNewsHttpClient
from src.clients.news_sources import NewsSourceClient, clean_text


PARAGRAPHS = [
    f"Section {index} explains how to build and evaluate a useful model. "
    "The experiment compares several implementations and discusses their measured limitations. "
    "The authors provide practical details to reproduce the experiment and verify the results."
    for index in range(3)
]


def extract(body: str) -> str:
    source = NewsSourceClient(AsyncMock(spec=SafeNewsHttpClient))
    return source._article(NewsHttpResponse(
        "https://example.org/post", 200, body.encode(), httpx.Headers(),
    ))[1]


@pytest.mark.parametrize("body_class", ["article-body", "notebody", "publication-content", "text-with-summary"])
def test_semantic_article_bodies_without_main_or_article(body_class):
    body = " ".join(PARAGRAPHS)
    html = f'<nav>Menu</nav><div class="{body_class}"><p>{body}</p><button>Share</button></div>'
    assert extract(html) == body


def test_transcript_in_layout_aside_survives_without_other_sidebar_text():
    body = " ".join(PARAGRAPHS)
    html = f'''<aside class="podcast__rightside"><div class="podcast__rightside-content">
      <p>{body}</p><aside>Related episodes</aside><button>Play</button></div></aside>
      <aside><div class="related">{'Unrelated recommendations. ' * 100}</div></aside>'''
    assert extract(html) == body


@pytest.mark.parametrize("wrapper", [
    '<div hidden>{body}</div>', '<div aria-hidden="true">{body}</div>',
    '<div role="dialog">{body}</div>', '<nav>{body}</nav>',
    '<div class="navigation">{body}</div>',
])
def test_preferred_body_does_not_resurrect_hidden_or_navigation_content(wrapper):
    body = '<div class="notebody"><p>' + " ".join(PARAGRAPHS) + '</p></div>'
    assert extract(wrapper.format(body=body)) == ""


def test_comment_separated_text_is_joined_without_breaking_words():
    text = "Sparse attention keeps the relevant context."
    fragmented = "<!--[--><!--]-->".join(text)
    assert clean_text(f'<p>{fragmented}</p><p>Second paragraph.</p>') == text + " Second paragraph."
    assert clean_text('<p>Keep <strong>real inline</strong> boundaries.</p>') == "Keep real inline boundaries."


def test_paper_abstract_excludes_votes_rank_and_discussion():
    abstract = " ".join(PARAGRAPHS)
    fragmented = "<!--]--><!--[-1-->".join(abstract)
    html = f'''<main><div data-target="PaperContent"><h1>Paper title</h1>
      <p>999 votes, #1 paper of the day</p><div><h2>Abstract</h2>
      <div><p>{fragmented}</p></div></div><section><h2>Discussion</h2>
      <p>{'Unrelated comments and user reactions. ' * 100}</p></section></div></main>'''
    assert extract(html) == abstract


def test_generated_div_layout_uses_substantial_prose_in_document_order():
    body = ''.join(f'<div class="_generated"><p>{text}</p></div>' for text in PARAGRAPHS)
    html = f'<div><h1>Article title</h1>{body}<footer><p>Legal notice</p></footer></div>'
    assert extract(html) == " ".join(PARAGRAPHS)


@pytest.mark.parametrize("body", [
    ''.join(f'<p><a href="/post">{text}</a></p>' for text in PARAGRAPHS),
    ''.join(f'<a href="/post"><p>{text}</p></a>' for text in PARAGRAPHS),
    ''.join(f'<p>{text}</p>' for text in PARAGRAPHS[:2]),
    f'<p>{PARAGRAPHS[0]}</p>' * 3,
])
def test_prose_fallback_rejects_link_lists_and_insufficient_unique_paragraphs(body):
    assert extract(f'<h1>Section title</h1><div>{body}</div>') == ""


def test_prose_fallback_requires_a_heading():
    assert extract(''.join(f'<p>{text}</p>' for text in PARAGRAPHS)) == ""


def test_habr_article_body_excludes_changing_views_and_relative_dates():
    body = " ".join(PARAGRAPHS)
    pages = [f'''<main><article><div>Author, {minutes} minutes ago. Views: {minutes * 100}</div>
      <div class="article-body"><div class="article-formatted-body"><p>{body}</p></div></div>
      <div>Comments: {minutes}</div></article></main>''' for minutes in (1, 9)]
    assert extract(pages[0]) == extract(pages[1]) == body


def test_blog_votes_and_author_controls_do_not_change_extracted_article():
    body = " ".join(PARAGRAPHS)
    pages = [f'''<div class="blog-content"><h1>Publication title</h1>
      <div class="not-prose"><div data-target="UpvoteControl">Upvote {count}</div></div>
      <div data-target="BlogAuthorsByline">Author Follow Followers: {count}</div>
      <div><p>{body}</p></div></div>''' for count in (8, 15)]
    assert extract(pages[0]) == extract(pages[1]) == "Publication title " + body


def test_rotating_promotions_and_related_events_do_not_change_article_text():
    pages = [f'''<article class="news_container"><h1>Publication title</h1>
      <p>{PARAGRAPHS[0]}</p><noindex><a class="promoblock" href="/promotion-{index}">
      <span class="promoblock__title">Promotion {index}</span></a></noindex>
      <p>{PARAGRAPHS[1]}</p><noindex><ul class="event_list"><li>
      <a href="/related-{index}">Random recommendation {index}</a></li></ul></noindex>
      <div class="article-bottom-info">Share Subscribe</div></article>''' for index in (1, 2)]
    assert extract(pages[0]) == extract(pages[1]) == "Publication title " + " ".join(PARAGRAPHS[:2])
