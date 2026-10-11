"""RSS/Atom and selector-based HTML adapters; no browser or script execution."""

import asyncio
import calendar
import hashlib
import io
import json
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser
from bs4 import BeautifulSoup, Tag
from soupsieve import SelectorSyntaxError

from src.clients.news_http import NewsHttpResponse, SafeNewsHttpClient, validate_public_url
from src.exceptions.news_sources import NewsSourceError
from src.schemas.news_collection import CollectedItem, CollectionResult, DiscoveryResult

TRACKING_PARAMETERS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid"}
HTML_HEADINGS = "h2, h3, h4, h5, h6, [itemprop='headline']"
HTML_TITLE_CLASS = re.compile(r"(?:^|[-_])title(?:$|[-_])", re.IGNORECASE)
HTML_NAVIGATION_CLASS = re.compile(r"(?:^|[-_])(?:nav|navbar|navigation|menu)(?:$|[-_])", re.IGNORECASE)
HTML_READ_MORE = re.compile(r"^(?:read more|learn more|continue reading|подробнее|читать далее)\W*$", re.IGNORECASE)
NON_ARTICLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js",
                        ".pdf", ".zip", ".mp3", ".mp4", ".xml", ".json"}


def normalize_url(value: str) -> str:
    """Normalize safe identity URLs without discarding meaningful query fields."""
    url = validate_public_url(value)
    parsed = urlsplit(str(url))
    pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(sorted(pairs)), ""))


def clean_text(value: str, *, limit: int = 20000) -> str:
    """Discard markup and navigation before retaining a bounded text fragment."""
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup.select("script, style, nav, header, footer, aside, form, noscript, template"):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()[:limit]


def prepare_collected_item(item: CollectedItem) -> dict[str, Any]:
    """Build the persistence payload; identity/hash do not depend on crawl time."""
    content = item.content or item.description
    fingerprint = json.dumps([item.title, item.description, content], ensure_ascii=False, separators=(",", ":"))
    return {
        "external_id": item.external_id,
        "url": item.url,
        "canonical_url": item.canonical_url,
        "normalized_url": normalize_url(item.canonical_url),
        "title": item.title,
        "excerpt": item.description,
        "content": content,
        "content_hash": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        "published_at": item.published_at,
        "updated_at": item.updated_at,
        "metadata_json": item.metadata,
    }


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            if len(value) > 40 or not re.search(r"\b\d{4}\b", value):
                return None
            for date_format in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
                try:
                    parsed = datetime.strptime(value.strip(), date_format)
                    break
                except ValueError:
                    continue
            else:
                return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _feed_date(entry: dict, key: str) -> datetime | None:
    parsed = entry.get(f"{key}_parsed") if f"{key}_parsed" in entry else None
    if parsed:
        try:
            return datetime.fromtimestamp(calendar.timegm(parsed), timezone.utc)
        except (ValueError, OverflowError, TypeError):
            return None
    return _parse_date(entry.get(key) if key in entry else None)


def _safe_link(base: str, value: str | None) -> str | None:
    if not value:
        return None
    try:
        return normalize_url(urljoin(base, value))
    except (NewsSourceError, ValueError, TypeError):
        return None


class NewsSourceClient:
    """Discover and collect sources through the shared public-only HTTP client."""

    SUFFICIENT_DESCRIPTION_CHARS = 600

    def __init__(self, http: SafeNewsHttpClient, max_excerpt_chars: int = 3000) -> None:
        self.http = http
        self.max_excerpt_chars = max_excerpt_chars

    async def discover(
        self, url: str, kind: str | None = None, config: dict | None = None,
    ) -> DiscoveryResult:
        """Detect feeds or preview HTML selectors, retaining at most five rows."""
        response = await self.http.get(url)
        self._require_ok(response)
        actual_kind, items = await asyncio.to_thread(self._parse, response, kind, config or {}, 5)
        warnings: list[str] = []
        if actual_kind == "html" and kind != "html":
            alternate = await asyncio.to_thread(self._find_feed, response)
            if alternate:
                try:
                    feed = await self.http.get(alternate)
                    self._require_ok(feed)
                    feed_kind, feed_items = await asyncio.to_thread(self._parse, feed, "rss", {}, 5)
                    if not feed_items:
                        raise NewsSourceError("empty_preview", "В обнаруженной ленте нет материалов.")
                except NewsSourceError:
                    if not items:
                        raise
                    warnings.append("Обнаруженная лента недоступна; показаны материалы HTML-страницы.")
                else:
                    actual_kind, items, response = feed_kind, feed_items, feed
        if not items:
            raise NewsSourceError("empty_preview", "Материалы не найдены. Уточните URL или CSS-селекторы.")
        if actual_kind == "html" and not (config or {}).get("item_selector"):
            warnings.append("Автоматический разбор HTML: проверьте карточки и при необходимости задайте селекторы.")
        return DiscoveryResult(actual_kind, normalize_url(response.url), items[:5], warnings)

    async def fetch(
        self, *, url: str, kind: str, config: dict, etag: str | None = None,
        last_modified: str | None = None, first_run: bool = False,
        max_items: int = 50, lookback_days: int = 30,
        max_excerpt_chars: int | None = None,
    ) -> CollectionResult:
        """Collect a bounded batch; conditional responses never remove stored items."""
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        response = await self.http.get(url, headers=headers)
        if response.status_code == 304:
            return CollectionResult([], etag, last_modified, True, response.url, kind)
        self._require_ok(response)
        adapter = self if max_excerpt_chars is None else NewsSourceClient(self.http, max_excerpt_chars)
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days) if first_run else None
        actual_kind, items = await asyncio.to_thread(adapter._parse, response, kind, config, max_items, cutoff)
        warnings: list[str] = []
        items = list(await asyncio.gather(*(adapter._enrich(item, warnings) for item in items)))
        return CollectionResult(
            items, response.headers.get("etag"), response.headers.get("last-modified"),
            False, response.url, actual_kind, list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _require_ok(response: NewsHttpResponse) -> None:
        if response.status_code != 200:
            raise NewsSourceError("http_status", f"Источник вернул HTTP {response.status_code}.")

    def _parse(
        self, response: NewsHttpResponse, kind: str | None, config: dict, limit: int,
        cutoff: datetime | None = None,
    ) -> tuple[str, list[CollectedItem]]:
        body = response.content
        if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", body, re.IGNORECASE) and kind == "rss":
            raise NewsSourceError("unsafe_xml", "Лента с объявлениями XML-сущностей не поддерживается.")
        is_feed = bool(re.search(br"<(?:[a-zA-Z]+:)?(?:rss|feed|RDF)(?:\s|>)", body[:4096]))
        if kind == "rss" or (kind is None and is_feed):
            if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", body, re.IGNORECASE):
                raise NewsSourceError("unsafe_xml", "Лента с объявлениями XML-сущностей не поддерживается.")
            return "rss", self._parse_feed(body, response.url, limit, cutoff)
        return "html", self._parse_html(body, response.url, config, limit, cutoff)

    def _parse_feed(self, body: bytes, base: str, limit: int, cutoff: datetime | None = None) -> list[CollectedItem]:
        # A bytes argument can be interpreted by feedparser as a local path.
        feed = feedparser.parse(io.BytesIO(body), resolve_relative_uris=False)
        if not feed.get("version"):
            raise NewsSourceError("invalid_feed", "Ответ не является RSS/Atom-лентой.")
        items: list[CollectedItem] = []
        seen: set[str] = set()
        for entry in feed.entries:
            external_id = str(entry.get("id") or entry.get("guid") or "")[:2048] or None
            url = _safe_link(base, entry.get("link"))
            if not url and external_id and external_id.startswith(("https://", "http://")):
                url = _safe_link(base, external_id)
            title = clean_text(str(entry.get("title", "")), limit=1000)
            if not url or not title or url in seen:
                continue
            published_at = _feed_date(entry, "published")
            if cutoff and published_at and published_at < cutoff:
                continue
            description = clean_text(str(entry.get("summary", "")), limit=self.max_excerpt_chars)
            contents = entry.get("content") or []
            content = clean_text(str(contents[0].get("value", "")), limit=self.max_excerpt_chars) if contents else ""
            if len(description) > len(content):
                content = description
            language = entry.get("language") or feed.feed.get("language") or ""
            items.append(CollectedItem(
                external_id, url, url, title, description, content,
                published_at, _feed_date(entry, "updated"),
                {"language": str(language)[:30], "method": "rss"},
            ))
            seen.add(url)
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _find_feed(response: NewsHttpResponse) -> str | None:
        soup = BeautifulSoup(response.content, "html.parser")
        candidates: list[str] = []
        for tag in soup.select('link[rel~="alternate"][href], a[rel~="alternate"][href]'):
            mime_type = str(tag.get("type", "")).split(";", 1)[0].strip().lower()
            if mime_type in {"application/rss+xml", "application/atom+xml", "application/rdf+xml"}:
                url = _safe_link(response.url, str(tag["href"]))
                if url:
                    candidates.append(url)
        page = urlsplit(response.url)
        # A category-specific alternate is more relevant than a site's global feed.
        page_parts = page.path.strip("/").split("/") if page.path.strip("/") else []

        def relevance(url: str) -> tuple[bool, int]:
            feed = urlsplit(url)
            common = 0
            for left, right in zip(page_parts, feed.path.strip("/").split("/")):
                if left != right:
                    break
                common += 1
            return feed.netloc == page.netloc, common

        return max(candidates, key=relevance) if candidates else None

    def _parse_html(self, body: bytes, base: str, config: dict, limit: int, cutoff: datetime | None = None) -> list[CollectedItem]:
        soup = BeautifulSoup(body, "html.parser")
        for tag in soup.select("script, style, nav, aside, form, template, "
                               "[role='navigation'], [role='banner'], [role='contentinfo'], [role='dialog']"):
            tag.decompose()
        for tag in soup.select("header, footer"):
            if not tag.find_parent(["article"]) and not tag.find_parent(class_=["post", "entry", "news-item"]):
                tag.decompose()
        try:
            automatic = not config.get("item_selector")
            nodes = self._html_candidates(soup) if automatic else soup.select(config["item_selector"])
            items: list[CollectedItem] = []
            seen: set[str] = set()
            for node in nodes:
                title_node = (self._html_title(node) if automatic and not config.get("title_selector")
                              else self._select(node, config.get("title_selector"), "h1, h2, h3, h4"))
                link = (self._html_link(node, title_node) if automatic and not config.get("link_selector")
                        else self._select(node, config.get("link_selector"), "a[href]"))
                if node.name == "a" and not config.get("link_selector"):
                    link = node
                url = _safe_link(base, str(link.get("href", ""))) if link else None
                if automatic and url and not self._is_article_url(url, base):
                    continue
                title = clean_text(str(title_node or link or ""), limit=1000)
                if automatic and (title_node is None or title_node is link) and link and link.get("title"):
                    title = clean_text(str(link["title"]), limit=1000)
                if not url or not title or url in seen:
                    continue
                excerpt_node = self._select(node, config.get("content_selector"), "p, .summary, .excerpt")
                excerpt = clean_text(str(excerpt_node or ""), limit=self.max_excerpt_chars)
                date_node = (self._html_date(node) if automatic and not config.get("date_selector")
                             else self._select(node, config.get("date_selector"), "time"))
                date_text = (str(date_node.get("datetime") or date_node.get_text(" ", strip=True)) if date_node else None)
                published_at = _parse_date(date_text)
                if cutoff and published_at and published_at < cutoff:
                    continue
                items.append(CollectedItem(
                    None, url, url, title, excerpt, excerpt, published_at, None,
                    {"language": str(soup.html.get("lang", ""))[:30] if soup.html else "", "method": "html"},
                ))
                seen.add(url)
                if len(items) >= limit:
                    break
            return items
        except (SelectorSyntaxError, ValueError, TypeError):
            raise NewsSourceError("invalid_selector", "Проверьте CSS-селекторы источника.") from None

    @staticmethod
    def _is_article_url(url: str, base: str) -> bool:
        if url == normalize_url(base):
            return False
        path = urlsplit(url).path.lower().rstrip("/")
        if not path:
            return False
        if any(path.endswith(suffix) for suffix in NON_ARTICLE_SUFFIXES):
            return False
        parts = path.strip("/").split("/")
        if parts[-1] in {"blog", "news", "articles", "publications", "writing", "our-work", "membership",
                         "about", "contact", "privacy", "privacy-policy", "terms", "login", "signup", "subscribe"}:
            return False
        return len(parts) < 2 or parts[-2] not in {
            "tag", "tags", "category", "categories", "topics", "site", "our-work",
        }

    @staticmethod
    def _html_date(node: Tag) -> Tag | None:
        for candidate in node.select("time, [itemprop='datePublished'], code, p, span"):
            value = str(candidate.get("datetime") or candidate.get_text(" ", strip=True))
            if _parse_date(value):
                return candidate
        return None

    @classmethod
    def _html_title(cls, node: Tag) -> Tag | None:
        if any(HTML_TITLE_CLASS.search(value) for value in node.get("class", [])):
            return node
        title = node.select_one(HTML_HEADINGS) or node.find(class_=HTML_TITLE_CLASS)
        if title:
            return title
        if node.name == "a":
            parent = node.find_parent(["h2", "h3", "h4", "h5", "h6"])
            parent = parent or node.find_parent(class_=HTML_TITLE_CLASS)
            if (parent and not parent.select_one("h1")
                    and parent.get_text(" ", strip=True) == node.get_text(" ", strip=True)):
                return node
            if cls._html_date(node):
                return next((p for p in node.select("p") if not _parse_date(p.get_text(" ", strip=True))), None)
        return None

    @staticmethod
    def _html_link(node: Tag, title: Tag | None) -> Tag | None:
        if node.name == "a":
            return node
        if title:
            link = title if title.name == "a" else title.select_one("a[href]")
            if link and title.get_text(" ", strip=True) == link.get_text(" ", strip=True):
                return link
            link = title.find_parent("a", href=True)
            if link:
                return link
        links = node.select("a[href]")
        if len({str(link["href"]) for link in links}) == 1:
            return links[0]
        return None

    @classmethod
    def _html_candidates(cls, soup: BeautifulSoup) -> list[Tag]:
        candidates: dict[int, Tag] = {}
        for node in soup.select("article, .post, .entry, .news-item, a[href]"):
            if len(node.select(HTML_HEADINGS)) > 1:
                continue
            title = cls._html_title(node)
            dated = cls._html_date(node)
            if (node.name == "a" and title is not None and title is not node and dated is None
                    and not node.select_one(HTML_HEADINGS) and not node.find_parent("article")):
                continue
            if title is not None or dated is not None:
                candidates[id(node)] = node
        # Some cards place their sole call-to-action beside, rather than around, the heading.
        for title in soup.select(HTML_HEADINGS):
            if title.find_parent("a", href=True) or title.select_one("a[href]"):
                continue
            node = title.parent
            for _ in range(4):
                if not isinstance(node, Tag) or node.name in {"body", "html", "main"}:
                    break
                if len(node.select(HTML_HEADINGS)) != 1:
                    break
                links = node.select("a[href]")
                if len({str(link["href"]) for link in links}) == 1:
                    if any(HTML_READ_MORE.fullmatch(link.get_text(" ", strip=True)) for link in links):
                        candidates[id(node)] = node
                    break
                node = node.parent
        return [node for node in soup.descendants if isinstance(node, Tag) and id(node) in candidates
                and not node.find_parent("h1") and not cls._html_navigation(node)]

    @staticmethod
    def _html_navigation(node: Tag) -> bool:
        for ancestor in [node, *node.parents]:
            if ancestor.name.endswith("-header") or any(
                HTML_NAVIGATION_CLASS.search(value) for value in ancestor.get("class", [])
            ):
                return True
        return False

    @staticmethod
    def _select(node: Tag, configured: str | None, fallback: str) -> Tag | None:
        if configured == ":scope":
            return node
        return node.select_one(configured or fallback)

    async def _enrich(self, item: CollectedItem, warnings: list[str]) -> CollectedItem:
        if len(item.content or item.description) >= self.SUFFICIENT_DESCRIPTION_CHARS:
            return item
        try:
            response = await self.http.get(item.url)
            self._require_ok(response)
            canonical, content = await asyncio.to_thread(self._article, response)
        except NewsSourceError:
            warnings.append("Часть страниц недоступна для получения текста; сохранены карточки источника.")
            return item
        return replace(item, canonical_url=canonical or item.canonical_url,
                       content=content if len(content) > len(item.content) else item.content)

    def _article(self, response: NewsHttpResponse) -> tuple[str | None, str]:
        soup = BeautifulSoup(response.content, "html.parser")
        canonical_tag = soup.select_one('link[rel~="canonical"][href]')
        canonical = _safe_link(response.url, str(canonical_tag["href"])) if canonical_tag else None
        # A cross-domain canonical is untrusted attribution, not proof of identity.
        if canonical and urlsplit(canonical).hostname != urlsplit(response.url).hostname:
            canonical = None
        node = soup.select_one("article") or soup.select_one("main")
        content = clean_text(str(node), limit=self.max_excerpt_chars) if node else ""
        return canonical, content
