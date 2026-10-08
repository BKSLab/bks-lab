"use client";

import Script from "next/script";
import { useEffect, useId } from "react";
import { adBlockId, type AdPlacement } from "@/lib/ads";

declare global {
  interface Window {
    yaContextCb?: Array<() => void>;
    Ya?: {
      Context?: {
        AdvManager?: {
          render: (options: { blockId: string; renderTo: string; darkTheme: boolean }) => void;
          destroy?: (options: { blockId: string }) => void;
        };
      };
    };
  }
}

export function AdSlot({
  placement,
  height = 300,
  className = "",
}: {
  placement: AdPlacement;
  height?: number;
  className?: string;
}) {
  const id = useId();
  const renderTo = `yandex-ad-${id.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const blockId = adBlockId(placement);

  useEffect(() => {
    if (!blockId) return;
    let active = true;
    let rendered = false;
    const render = () => {
      const manager = window.Ya?.Context?.AdvManager;
      if (!active || !manager || rendered) return;
      try {
        manager.render({
          blockId,
          renderTo,
          darkTheme: document.documentElement.dataset.theme === "dark",
        });
        rendered = true;
      } catch {
        // A blocked or failed provider must not interrupt reading the page.
      }
    };
    if (window.Ya?.Context?.AdvManager) render();
    else (window.yaContextCb ??= []).push(render);
    return () => {
      active = false;
      if (rendered) {
        try {
          window.Ya?.Context?.AdvManager?.destroy?.({ blockId });
        } catch {
          // Third-party cleanup must not interrupt route navigation.
        }
      }
    };
  }, [blockId, renderTo]);

  if (!blockId) return null;
  return (
    <aside
      aria-label="Реклама"
      data-ad-placement={placement}
      className={`flex min-w-0 flex-col rounded-card border border-border bg-surface ${className}`}
      style={{ height }}
    >
      <p className="shrink-0 px-3 py-1 text-xs text-text-muted">Реклама</p>
      <div id={renderTo} className="min-h-0 flex-1 overflow-auto" style={{ maxHeight: height - 28 }} />
      {/* Next Script deduplicates this shared loader across slots and navigation. */}
      <Script id="yandex-ad-context" src="https://yandex.ru/ads/system/context.js" strategy="lazyOnload" />
    </aside>
  );
}
