"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";

/** Renew the HttpOnly cookie in the browser, which an RSC fetch cannot do. */
export function AdminSessionRefresh() {
  const pathname = usePathname();
  const router = useRouter();
  const lastRefresh = useRef(0);

  useEffect(() => {
    let disposed = false;
    let pending = false;
    let expired = false;
    const controller = new AbortController();

    async function refresh() {
      if (
        disposed || pending || expired || document.visibilityState === "hidden" ||
        Date.now() - lastRefresh.current < 5 * 60 * 1000
      ) return;
      pending = true;
      lastRefresh.current = Date.now();
      try {
        const response = await fetch("/api/admin/auth/me", {
          cache: "no-store",
          credentials: "same-origin",
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]),
        });
        if (!disposed && response.status === 401) {
          expired = true;
          router.replace("/admin/login");
          router.refresh();
        }
      } catch {
        // Transient failures are handled by the next page request or activity.
      } finally {
        pending = false;
      }
    }

    void refresh();
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    document.addEventListener("pointerdown", refresh);
    document.addEventListener("keydown", refresh);
    return () => {
      disposed = true;
      if (pending) lastRefresh.current = 0;
      controller.abort();
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
      document.removeEventListener("pointerdown", refresh);
      document.removeEventListener("keydown", refresh);
    };
  }, [pathname, router]);

  return null;
}
