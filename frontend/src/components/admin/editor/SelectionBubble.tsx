"use client";

import { Bold, Italic, Link as LinkIcon, TextQuote, Code, type LucideIcon } from "lucide-react";

import type { MarkdownAction } from "./markdown-actions";

const bubbleActions: { action: MarkdownAction; ariaLabel: string; Icon: LucideIcon }[] = [
  { action: "bold", ariaLabel: "Жирный", Icon: Bold },
  { action: "italic", ariaLabel: "Курсив", Icon: Italic },
  { action: "link", ariaLabel: "Ссылка", Icon: LinkIcon },
  { action: "quote", ariaLabel: "Цитата", Icon: TextQuote },
  { action: "code", ariaLabel: "Код", Icon: Code },
];

/** Floating action bar shown above the current text selection in the editor. */
export function SelectionBubble({ top, left, onAction }: {
  top: number;
  left: number;
  onAction: (action: MarkdownAction) => void;
}) {
  return (
    <div
      className="editor-bubble"
      role="toolbar"
      aria-label="Действия с выделенным фрагментом"
      style={{ top, left }}
    >
      {bubbleActions.map(({ action, ariaLabel, Icon }) => (
        <button
          key={action}
          type="button"
          className="editor-toolbar-button"
          aria-label={ariaLabel}
          title={ariaLabel}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onAction(action)}
        >
          <Icon size={18} aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
