"""Audit catalogue URLs with the production client, without DB writes or LLM calls."""

import argparse
import asyncio
from collections import Counter
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

from src.core.news_settings import NewsSettings
from src.dependencies.news_clients import news_source_client
from src.exceptions.news_sources import NewsSourceError


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


async def audit(args: argparse.Namespace, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Run bounded requests, recording safe headers and short previews only."""
    settings = NewsSettings()
    targets = audit_targets(entries)
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
                    "url": str(response.request.url), "status": response.status_code,
                    "encoding": response.headers.get("content-encoding"),
                    "type": response.headers.get("content-type"),
                    "length": response.headers.get("content-length"),
                    "location": response.headers.get("location"),
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
                    row.setdefault("documents", []).append({"url": response.url, "file": name})
            return response

        source.http.get = capture

        async def run(target: dict[str, Any]) -> None:
            async with semaphore:
                row = {**target, "requests": []}
                token = current.set(row)
                started = time.monotonic()
                stage = "discovery" if target["discover"] else "access"
                try:
                    async with asyncio.timeout(args.timeout):
                        if target["discover"]:
                            preview = await source.discover(target["url"], target["kind"])
                            row.update(status="preview", result=preview.to_dict())
                            if args.collect:
                                stage = "collection"
                                batch = await source.fetch(url=preview.url, kind=preview.kind, config={},
                                                           max_items=3, lookback_days=3650)
                                row["collection"] = {
                                    "status": "passed",
                                    "count": len(batch.items),
                                    "items": [item.to_dict() for item in batch.items],
                                    "warnings": batch.warnings,
                                }
                        else:
                            response = await source.http.get(target["url"])
                            source._require_ok(response)
                            row.update(status="reference_accessible", final_url=response.url)
                except NewsSourceError as error:
                    failure = {"status": "failed", "error_code": error.code, "error": str(error),
                               "retryable": error.retryable}
                    if stage == "collection":
                        row["collection"] = failure
                    else:
                        row.update(failure)
                except TimeoutError:
                    failure = {"status": "failed", "error_code": "audit_timeout", "error": "Audit time limit exceeded"}
                    if stage == "collection":
                        row["collection"] = failure
                    else:
                        row.update(failure)
                except Exception as error:
                    failure = {"status": "error", "error_code": type(error).__name__}
                    if stage == "collection":
                        row["collection"] = failure
                    else:
                        row.update(failure)
                finally:
                    current.reset(token)
                row["seconds"] = round(time.monotonic() - started, 2)
                results.append(row)
                print(f"{len(results)}/{len(targets)} {row['status']} "
                      f"{row.get('error_code', '')} {target['url']}", file=sys.stderr, flush=True)

        await asyncio.gather(*(run(target) for target in targets))
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(), "catalogue_rows": len(entries),
        "targets": len(targets), "collect": args.collect,
        "limits": {"timeout_seconds": settings.http_timeout_seconds,
                   "max_response_bytes": settings.http_max_response_bytes,
                   "max_redirects": settings.http_max_redirects, "audit_timeout": args.timeout},
        "summary": dict(Counter(row.get("error_code", row["status"]) for row in results)),
        "results": sorted(results, key=lambda row: row["url"]),
    }


def main() -> None:
    """Provide a repeatable read-only audit from the host or the backend container."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", required=True, help="TypeScript/JSON path, or - for stdin")
    parser.add_argument("--output", required=True)
    parser.add_argument("--documents-dir", help="Optional temporary directory for downloaded public documents")
    parser.add_argument("--only", help="Comma-separated catalogue IDs")
    parser.add_argument("--collect", action="store_true", help="Also collect up to three items per discovered source")
    parser.add_argument("--concurrency", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    raw = sys.stdin.read() if args.catalogue == "-" else Path(args.catalogue).read_text(encoding="utf-8")
    report = asyncio.run(audit(args, read_catalogue(raw)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
