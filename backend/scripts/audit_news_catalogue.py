"""Audit catalogue URLs with the production client, without DB writes or LLM calls."""

import argparse
import asyncio
from collections import Counter
from contextvars import ContextVar
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.clients.news_sources import normalize_url, prepare_collected_item
from src.core.news_settings import NewsSettings
from src.dependencies.news_clients import news_source_client
from src.exceptions.news_sources import NewsSourceError
from src.news_sources import get_source_profiles
from src.schemas.news_collection import NEWS_MIN_CONTENT_CHARS, CollectionResult

AUDIT_LOOKBACK_DAYS = 3650
QUALITY_STATUSES = ("ready", "fetch_failed", "insufficient_text")
IDENTITY_WARNING = "Разные URL материалов имеют одинаковый canonical URL; проверьте идентичность карточек."


def report_url(value: str | None) -> str | None:
    """Redact transient authorization parameters from public redirect diagnostics."""
    if not value:
        return value
    parts = urlsplit(value)
    pairs = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        normalized = key.casefold().replace("-", "_")
        sensitive = (normalized in {"code", "state", "api_key", "apikey", "authorization"}
                     or any(word in normalized for word in ("token", "password", "secret")))
        pairs.append((key, "[redacted]" if sensitive else item))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))


def read_catalogue(value: str) -> list[dict[str, Any]]:
    """Read the existing JSON-compatible TypeScript array or an exported JSON array."""
    value = value.lstrip("\ufeff").strip()
    if not value.startswith("["):
        marker = "export const sourceCatalogue: SourceCatalogueEntry[] = "
        value = value.split(marker, 1)[1].lstrip()
    entries, _ = json.JSONDecoder().raw_decode(value)
    if not isinstance(entries, list) or not all(isinstance(row, dict) for row in entries):
        raise ValueError("Expected a catalogue array")
    return entries


def audit_targets(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cover every unique primary, feed and supplementary URL, preserving all row IDs."""
    targets: dict[str, dict[str, Any]] = {}
    for entry in entries:
        primary = entry.get("feedUrl") or entry["url"]
        for url in dict.fromkeys([entry["url"], primary, *entry.get("extraUrls", [])]):
            target = targets.setdefault(url, {"url": url, "entry_ids": [], "primary_ids": [],
                                              "discover": False, "kind": None})
            target["entry_ids"].append(entry["id"])
            if url == primary:
                target["primary_ids"].append(entry["id"])
            if entry["mode"] in {"rss", "auto"}:
                target["discover"] = True
                if entry["mode"] == "rss" and url == primary:
                    target["kind"] = "rss"
    return list(targets.values())


def identity_summary(batch: CollectionResult) -> dict[str, Any]:
    """Expose canonical collisions instead of silently collapsing different source URLs."""
    counts: Counter[str] = Counter()
    original_urls: dict[str, set[str]] = {}
    text_urls: dict[str, set[str]] = {}
    for item in batch.items:
        identity = prepare_collected_item(item)["normalized_url"]
        counts[identity] += 1
        original_urls.setdefault(identity, set()).add(normalize_url(item.url))
        text = " ".join((item.content or item.description).casefold().split())
        if len(text) >= NEWS_MIN_CONTENT_CHARS:
            signature = hashlib.sha256(text.encode()).hexdigest()
            text_urls.setdefault(signature, set()).add(identity)
    return {
        "repeated_identities": sum(count > 1 for count in counts.values()),
        "collision_urls": sorted(identity for identity, urls in original_urls.items() if len(urls) > 1),
        "duplicate_text_urls": [sorted(urls) for urls in text_urls.values() if len(urls) > 1],
    }


def collection_result(batch: CollectionResult) -> dict[str, Any]:
    """Describe extraction quality separately from a successful HTTP/discovery result."""
    quality = dict.fromkeys(QUALITY_STATUSES, 0)
    warnings = list(batch.warnings)
    for item in batch.items:
        status = item.metadata.get("collection_status")
        enough_text = max(len(item.content), len(item.description)) >= NEWS_MIN_CONTENT_CHARS
        if status not in QUALITY_STATUSES or (status == "ready" and not enough_text):
            status = "ready" if enough_text else "insufficient_text"
        quality[status] += 1
        if item.metadata.get("collection_warning"):
            warnings.append(item.metadata["collection_warning"])
    identities = identity_summary(batch)
    if identities["collision_urls"]:
        warnings.append(IDENTITY_WARNING)
    if identities["duplicate_text_urls"]:
        warnings.append("Разные публикации содержат одинаковый текст; проверьте извлечение статьи.")
    warnings = list(dict.fromkeys(warnings))
    if batch.not_modified:
        status = "not_modified"
    elif not batch.items:
        status = "empty"
    elif warnings or quality["fetch_failed"] or quality["insufficient_text"]:
        status = "degraded"
    else:
        status = "passed"
    return {
        "status": status, "count": len(batch.items), "items": [item.to_dict() for item in batch.items],
        "warnings": warnings, "quality": quality, "not_modified": batch.not_modified, **identities,
    }


def compare_collections(first: CollectionResult | None, second: CollectionResult | None) -> dict[str, Any]:
    """Compare observed identities and text versions without inferring semantic duplication."""
    if first is None or second is None:
        return {"status": "unavailable", "reason": "collection_failed"}
    if first.not_modified or second.not_modified:
        return {"status": "unavailable", "reason": "not_modified"}
    if not first.items or not second.items:
        return {"status": "unavailable", "reason": "empty_batch"}

    def versions(batch: CollectionResult) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for item in batch.items:
            data = prepare_collected_item(item)
            result.setdefault(data["normalized_url"], set()).add(data["content_hash"])
        return result

    before, after = versions(first), versions(second)
    common = before.keys() & after.keys()
    groups = {
        "new": after.keys() - before.keys(),
        "disappeared": before.keys() - after.keys(),
        "changed": {url for url in common if before[url] != after[url]},
        "unchanged": {url for url in common if before[url] == after[url]},
    }
    first_identity, second_identity = identity_summary(first), identity_summary(second)
    collisions = sorted(set(first_identity["collision_urls"]) | set(second_identity["collision_urls"]))
    result = {
        "status": "ambiguous" if collisions else "compared", "common": len(common),
        "collision_urls": collisions, "warnings": [IDENTITY_WARNING] if collisions else [],
        "repeated_identities": {"first": first_identity["repeated_identities"], "repeat": second_identity["repeated_identities"]},
    }
    for name, urls in groups.items():
        result[name] = len(urls)
        result[f"{name}_urls"] = sorted(urls)
    return result


def collection_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate both passes independently so discovery success cannot hide collection failures."""
    summary: dict[str, Any] = {}
    for name, field in (("first", "collection"), ("repeat", "repeat_collection")):
        batches = [row[field] for row in results if field in row]
        summary[name] = {
            "statuses": dict(Counter(batch["status"] for batch in batches)),
            "quality": {status: sum(batch.get("quality", {}).get(status, 0) for batch in batches) for status in QUALITY_STATUSES},
            "warnings": sum(len(batch.get("warnings", [])) for batch in batches),
            "repeated_identities": sum(batch.get("repeated_identities", 0) for batch in batches),
            "collisions": sum(len(batch.get("collision_urls", [])) for batch in batches),
        }
    comparisons = [row["comparison"] for row in results if "comparison" in row]
    summary["comparison"] = {
        "statuses": dict(Counter(row["status"] for row in comparisons)),
        **{name: sum(row.get(name, 0) for row in comparisons) for name in ("new", "disappeared", "changed", "unchanged")},
    }
    return summary


async def audit(args: argparse.Namespace, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Run bounded requests, recording safe headers and short previews only."""
    settings = NewsSettings()
    repeat_collect = getattr(args, "repeat_collect", False)
    lookback_days = getattr(args, "lookback_days", AUDIT_LOOKBACK_DAYS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    use_profiles = getattr(args, "profiles", False)
    targets = ([{
        "url": profile.url, "entry_ids": list(profile.research_ids or (profile.id,)),
        "primary_ids": [profile.id], "profile_id": profile.id,
        "discover": False, "kind": profile.kind,
    } for profile in get_source_profiles()] if use_profiles else audit_targets(entries))
    if args.only:
        selected = set(args.only.split(","))
        targets = [row for row in targets if selected.intersection(row["entry_ids"])]
    semaphore = asyncio.Semaphore(args.concurrency)
    current: ContextVar[dict[str, Any] | None] = ContextVar("audit_target", default=None)
    documents = Path(args.documents_dir) if args.documents_dir else None
    if documents:
        documents.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    async with news_source_client(settings) as source:
        async def observe(response: Any) -> None:
            row = current.get()
            if row is not None:
                row["requests"].append({
                    "url": report_url(str(response.request.url)), "status": response.status_code,
                    "encoding": response.headers.get("content-encoding"),
                    "type": response.headers.get("content-type"),
                    "length": response.headers.get("content-length"),
                    "location": report_url(response.headers.get("location")),
                })

        source.http.client.event_hooks["response"].append(observe)
        original_get = source.http.get

        async def capture(url: str, **kwargs: Any) -> Any:
            response = await original_get(url, **kwargs)
            if documents and response.status_code == 200:
                name = hashlib.sha256(response.url.encode()).hexdigest()[:20] + ".body"
                (documents / name).write_bytes(response.content)
                row = current.get()
                if row is not None:
                    row.setdefault("documents", []).append({"url": report_url(response.url), "file": name})
            return response

        source.http.get = capture

        async def collect(
            url: str, kind: str, known_urls: set[str], profile_id: str | None = None,
        ) -> tuple[CollectionResult | None, dict[str, Any]]:
            try:
                options = dict(max_items=3, lookback_days=lookback_days,
                               cutoff=cutoff, known_urls=known_urls)
                batch = (await source.fetch_profile(profile_id, **options) if profile_id
                         else await source.fetch(url=url, kind=kind, config={}, **options))
                if profile_id and getattr(args, "verify_articles", False) and batch.items:
                    articles = await source.refetch(batch.items, profile_id=profile_id)
                    batch = replace(batch, items=articles.items,
                                    warnings=list(dict.fromkeys([*batch.warnings, *articles.warnings])))
                return batch, collection_result(batch)
            except NewsSourceError as error:
                return None, {"status": "failed", "error_code": error.code, "error": str(error), "retryable": error.retryable}
            except TimeoutError:
                return None, {"status": "failed", "error_code": "audit_timeout", "error": "Audit time limit exceeded"}
            except Exception as error:
                return None, {"status": "error", "error_code": type(error).__name__}

        async def run(target: dict[str, Any]) -> None:
            async with semaphore:
                row = {**target, "requests": []}
                token = current.set(row)
                started = time.monotonic()
                stage = "discovery" if target["discover"] else "access"
                try:
                    async with asyncio.timeout(args.timeout):
                        if target["discover"] or target.get("profile_id"):
                            if target.get("profile_id"):
                                row.update(status="profile", result={"url": target["url"], "kind": target["kind"]})
                                collected_url, collected_kind = target["url"], target["kind"]
                            else:
                                preview = await source.discover(target["url"], target["kind"])
                                row.update(status="preview", result=preview.to_dict())
                                collected_url, collected_kind = preview.url, preview.kind
                            if args.collect:
                                stage = "collection"
                                first, row["collection"] = await collect(
                                    collected_url, collected_kind, set(), target.get("profile_id"),
                                )
                                if repeat_collect:
                                    stage = "repeat_collection"
                                    known_urls = {
                                        normalize_url(url) for item in (first.items if first else [])
                                        for url in (item.url, item.canonical_url)
                                    }
                                    second, row["repeat_collection"] = await collect(
                                        collected_url, collected_kind, known_urls, target.get("profile_id"),
                                    )
                                    row["comparison"] = compare_collections(first, second)
                        else:
                            response = await source.http.get(target["url"])
                            source._require_ok(response)
                            row.update(status="reference_accessible", final_url=response.url)
                except NewsSourceError as error:
                    failure = {"status": "failed", "error_code": error.code, "error": str(error),
                               "retryable": error.retryable}
                    if stage in {"collection", "repeat_collection"}:
                        row[stage] = failure
                    else:
                        row.update(failure)
                except TimeoutError:
                    failure = {"status": "failed", "error_code": "audit_timeout", "error": "Audit time limit exceeded"}
                    if stage in {"collection", "repeat_collection"}:
                        row[stage] = failure
                    else:
                        row.update(failure)
                except Exception as error:
                    failure = {"status": "error", "error_code": type(error).__name__}
                    if stage in {"collection", "repeat_collection"}:
                        row[stage] = failure
                    else:
                        row.update(failure)
                finally:
                    current.reset(token)
                if repeat_collect and "collection" in row:
                    row.setdefault("repeat_collection", {"status": "skipped", "reason": "audit_timeout"})
                    row.setdefault("comparison", {"status": "unavailable", "reason": "collection_failed"})
                row["seconds"] = round(time.monotonic() - started, 2)
                results.append(row)
                print(f"{len(results)}/{len(targets)} {row['status']} "
                      f"{row.get('error_code', '')} {target['url']}", file=sys.stderr, flush=True)

        await asyncio.gather(*(run(target) for target in targets))
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(), "catalogue_rows": len(entries),
        "curated_profiles": len(targets) if use_profiles else 0,
        "targets": len(targets), "collect": args.collect, "repeat_collect": repeat_collect,
        "limits": {"timeout_seconds": settings.http_timeout_seconds,
                   "max_response_bytes": settings.http_max_response_bytes,
                   "max_redirects": settings.http_max_redirects, "audit_timeout": args.timeout,
                   "collection_items": 3, "collection_lookback_days": lookback_days, "collection_cutoff": cutoff.isoformat()},
        "summary": dict(Counter(row.get("error_code", row["status"]) for row in results)),
        "collection_summary": collection_summary(results),
        "results": sorted(results, key=lambda row: row["url"]),
    }


def main() -> None:
    """Provide a repeatable read-only audit from the host or the backend container."""
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--catalogue", help="TypeScript/JSON research candidates path, or - for stdin")
    selection.add_argument("--profiles", action="store_true", help="Audit code-owned supported source adapters")
    parser.add_argument("--output", required=True)
    parser.add_argument("--documents-dir", help="Optional temporary directory for downloaded public documents")
    parser.add_argument("--only", help="Comma-separated catalogue IDs")
    parser.add_argument("--collect", action="store_true", help="Also collect up to three items per discovered source")
    parser.add_argument("--repeat-collect", action="store_true", help="Repeat collection without conditional headers and compare text versions (requires --collect)")
    parser.add_argument("--verify-articles", action="store_true", help="Fetch and verify article bodies even when the profile feed contains sufficient text")
    parser.add_argument("--lookback-days", type=int, default=AUDIT_LOOKBACK_DAYS, help="History window; use 30 to verify normal initial collection")
    parser.add_argument("--concurrency", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.repeat_collect and not args.collect:
        parser.error("--repeat-collect requires --collect")
    if args.verify_articles and not (args.profiles and args.collect):
        parser.error("--verify-articles requires --profiles and --collect")
    if args.lookback_days < 1:
        parser.error("--lookback-days must be positive")
    entries = []
    if args.catalogue:
        raw = sys.stdin.read() if args.catalogue == "-" else Path(args.catalogue).read_text(encoding="utf-8")
        entries = read_catalogue(raw)
    report = asyncio.run(audit(args, entries))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    if args.collect:
        print(json.dumps({"collection_summary": report["collection_summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
