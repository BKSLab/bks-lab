"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { NewsRequestError, newsRequest } from "@/lib/news-api/client";
import type { NewsCollectionStatus } from "@/lib/news-api/types";

export function useNewsCollection(initialStatus: NewsCollectionStatus) {
  const router = useRouter();
  const [status, setStatus] = useState(initialStatus);
  const [error, setError] = useState("");
  const [requestedJob, setRequestedJob] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const latest = useRef(initialStatus);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let inFlight = false;
    let stopped = false;

    async function poll() {
      if (controller.signal.aborted || stopped || document.hidden || inFlight) return;
      clearTimeout(timer);
      inFlight = true;
      let failed = false;
      try {
        const query = requestedJob ? `?job_slug=${encodeURIComponent(requestedJob)}` : "";
        const next = await newsRequest<NewsCollectionStatus>(`/collection-status${query}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        latest.current = next;
        setStatus(next);
        setError("");
        if (requestedJob && next.job?.slug === requestedJob && !next.busy && next.job.status !== "queued" && next.job.status !== "running") setRequestedJob(null);
      } catch (reason) {
        if (controller.signal.aborted) return;
        failed = true;
        if (reason instanceof NewsRequestError && reason.status === 401) {
          stopped = true;
          router.replace("/admin/login");
          router.refresh();
        }
        setError(reason instanceof NewsRequestError ? reason.message : "Не удалось обновить состояние проверки.");
      } finally {
        inFlight = false;
        if (!controller.signal.aborted && !stopped && !document.hidden) {
          timer = setTimeout(poll, failed ? 5000 : latest.current.busy ? 2500 : 15000);
        }
      }
    }

    function wake() {
      clearTimeout(timer);
      if (!document.hidden) void poll();
    }

    document.addEventListener("visibilitychange", wake);
    window.addEventListener("focus", wake);
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("focus", wake);
    };
  }, [requestedJob, revision, router]);

  return {
    status,
    error,
    awaiting: requestedJob !== null && status.job?.slug !== requestedJob,
    requestedJob,
    watch: (slug: string) => { setRequestedJob(slug); setRevision(value => value + 1); },
    refresh: () => setRevision(value => value + 1),
  };
}
