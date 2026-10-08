"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";

const PAGEVIEW_URL = "/api/v1/stats/pageview";
// Public layouts can remount within one document, for example through a 404.
const viewedDocuments = new WeakSet<Document>();

interface PageViewBody {
  path: string;
  referrer?: string;
}

// Sends one pageview beacon per navigation (docs/api_contract.md,
// POST /stats/pageview). The ref-based dedup absorbs the StrictMode double
// effect in dev. referrer is sent only with the first pageview in the document;
// the URL hash (e.g. #note-<slug>) is read at send time. Hash-only
// navigation is not a pageview; note impressions belong to the notes feed.
export function PageViewTracker() {
  const pathname = usePathname();
  const query = useSearchParams()?.toString();
  const lastSentRef = useRef<string | null>(null);

  useEffect(() => {
    const path = `${pathname}${query ? `?${query}` : ""}${window.location.hash}`;

    if (lastSentRef.current === path) {
      return;
    }
    lastSentRef.current = path;

    const body: PageViewBody = { path };
    if (!viewedDocuments.has(document)) {
      viewedDocuments.add(document);
      if (document.referrer) {
        body.referrer = document.referrer;
      }
    }

    const blob = new Blob([JSON.stringify(body)], {
      type: "application/json",
    });
    navigator.sendBeacon(PAGEVIEW_URL, blob);
  }, [pathname, query]);

  return null;
}
