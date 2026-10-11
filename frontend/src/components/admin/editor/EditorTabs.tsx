"use client";

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export type EditorTab = { key: string; label: string; content: ReactNode };

/** Accessible tablist: panels mount lazily on first activation and stay mounted afterwards. */
export function EditorTabs({ tabs, active, onChange, ariaLabel }: {
  tabs: EditorTab[];
  active: string;
  onChange: (key: string) => void;
  ariaLabel: string;
}) {
  const baseId = useId();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [visited, setVisited] = useState<ReadonlySet<string>>(() => new Set([active]));
  if (!visited.has(active)) {
    setVisited(new Set(visited).add(active));
  }

  function onKeyDown(event: KeyboardEvent) {
    const index = tabs.findIndex((tab) => tab.key === active);
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    if (next === -1) return;
    event.preventDefault();
    const key = tabs[next].key;
    onChange(key);
    tabRefs.current[key]?.focus();
  }

  return (
    <div className="editor-tabs">
      <div className="editor-tablist" role="tablist" aria-label={ariaLabel} onKeyDown={onKeyDown}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            id={`${baseId}-${tab.key}-tab`}
            aria-controls={`${baseId}-${tab.key}-panel`}
            aria-selected={active === tab.key}
            tabIndex={active === tab.key ? 0 : -1}
            className="editor-tab"
            ref={(element) => { tabRefs.current[tab.key] = element; }}
            onClick={() => onChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.key}
          role="tabpanel"
          id={`${baseId}-${tab.key}-panel`}
          aria-labelledby={`${baseId}-${tab.key}-tab`}
          hidden={active !== tab.key}
          tabIndex={0}
          className="editor-tabpanel"
        >
          {visited.has(tab.key) ? tab.content : null}
        </div>
      ))}
    </div>
  );
}
