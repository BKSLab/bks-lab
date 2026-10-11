"use client";

import { useId, useMemo, useRef, useState } from "react";
import CodeMirror, { EditorView } from "@uiw/react-codemirror";
import { markdown } from "@codemirror/lang-markdown";
import {
  Bold, Italic, Heading2, Heading3, TextQuote, Link as LinkIcon,
  List, ListOrdered, Code, Image as ImageIcon, Megaphone, type LucideIcon,
} from "lucide-react";

import { applyMarkdownAction, insertBlockAtCursor, type MarkdownAction } from "./markdown-actions";
import { ImageInsertDialog } from "./ImageInsertDialog";
import { SelectionBubble } from "./SelectionBubble";

const toolbarButtons: { action: MarkdownAction; ariaLabel: string; Icon: LucideIcon }[] = [
  { action: "bold", ariaLabel: "Жирный", Icon: Bold },
  { action: "italic", ariaLabel: "Курсив", Icon: Italic },
  { action: "heading2", ariaLabel: "Заголовок второго уровня", Icon: Heading2 },
  { action: "heading3", ariaLabel: "Заголовок третьего уровня", Icon: Heading3 },
  { action: "quote", ariaLabel: "Цитата", Icon: TextQuote },
  { action: "link", ariaLabel: "Ссылка", Icon: LinkIcon },
  { action: "listBullet", ariaLabel: "Маркированный список", Icon: List },
  { action: "listNumber", ariaLabel: "Нумерованный список", Icon: ListOrdered },
  { action: "code", ariaLabel: "Код", Icon: Code },
];

type BubblePosition = { top: number; left: number };

export function MarkdownEditor({ value, onChange, disabled = false, placeholder = "Текст материала в Markdown…" }: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const labelId = useId();
  const viewRef = useRef<EditorView | null>(null);
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const [bubble, setBubble] = useState<BubblePosition | null>(null);
  const pendingCursorRef = useRef<{ from: number; to: number } | null>(null);

  const selectionTracker = useMemo(() => EditorView.updateListener.of((update) => {
    if (!update.selectionSet && !update.docChanged && !update.viewportChanged && !update.geometryChanged) return;
    const range = update.view.state.selection.main;
    const surface = update.view.dom.parentElement;
    let next: BubblePosition | null = null;
    if (!range.empty && surface) {
      const start = update.view.coordsAtPos(range.from);
      const end = update.view.coordsAtPos(range.to);
      if (start && end) {
        const box = surface.getBoundingClientRect();
        next = { top: start.top - box.top, left: (start.left + end.left) / 2 - box.left };
      }
    }
    setBubble((previous) => {
      if (previous && next && previous.top === next.top && previous.left === next.left) return previous;
      if (previous === next) return previous;
      return next;
    });
  }), []);

  function dispatchText(text: string, selectionStart: number, selectionEnd: number) {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: text },
      selection: { anchor: selectionStart, head: selectionEnd },
      scrollIntoView: true,
      userEvent: "input",
    });
    view.focus();
  }

  function runAction(action: MarkdownAction) {
    const view = viewRef.current;
    if (!view || disabled) return;
    const { from, to } = view.state.selection.main;
    const result = applyMarkdownAction(view.state.doc.toString(), from, to, action);
    dispatchText(result.text, result.selectionStart, result.selectionEnd);
  }

  function insertBlock(block: string, range: { from: number; to: number }) {
    const view = viewRef.current;
    if (!view || disabled) return;
    const result = insertBlockAtCursor(view.state.doc.toString(), range.from, range.to, block);
    dispatchText(result.text, result.selectionStart, result.selectionEnd);
  }

  function insertAdBlock() {
    const view = viewRef.current;
    if (!view || disabled) return;
    const { from, to } = view.state.selection.main;
    insertBlock("::ad", { from, to });
  }

  function openImageDialog() {
    const view = viewRef.current;
    if (!view || disabled) return;
    pendingCursorRef.current = view.state.selection.main;
    setBubble(null);
    setImageDialogOpen(true);
  }

  function handleImageInsert(markdownSnippet: string) {
    const range = pendingCursorRef.current;
    pendingCursorRef.current = null;
    if (!range) return;
    insertBlock(markdownSnippet, range);
  }

  return (
    <div className="editor-field admin-field">
      <span className="editor-field-label" id={labelId}>Текст материала (Markdown)</span>
      <div className="editor-toolbar" role="toolbar" aria-label="Разметка текста">
        {toolbarButtons.map(({ action, ariaLabel, Icon }) => (
          <button
            key={action}
            type="button"
            className="editor-toolbar-button"
            aria-label={ariaLabel}
            title={ariaLabel}
            disabled={disabled}
            onClick={() => runAction(action)}
          >
            <Icon size={18} aria-hidden="true" />
          </button>
        ))}
        <button type="button" className="editor-toolbar-button" aria-label="Изображение" title="Изображение" disabled={disabled} onClick={openImageDialog}>
          <ImageIcon size={18} aria-hidden="true" />
        </button>
        <button type="button" className="editor-toolbar-button" aria-label="Рекламный блок" title="Рекламный блок" disabled={disabled} onClick={insertAdBlock}>
          <Megaphone size={18} aria-hidden="true" />
        </button>
      </div>
      <div className="editor-surface">
        <CodeMirror
          className="editor-cm"
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          theme="none"
          editable={!disabled}
          basicSetup={{ lineNumbers: true, foldGutter: false }}
          extensions={[markdown(), selectionTracker, EditorView.contentAttributes.of({ "aria-labelledby": labelId, spellcheck: "true" })]}
          onCreateEditor={(view) => { viewRef.current = view; }}
        />
        {bubble && !disabled && (
          <SelectionBubble top={bubble.top} left={bubble.left} onAction={runAction} />
        )}
      </div>
      <p className="admin-muted">Заголовки внутри материала начинаются с ##. Изображения вставляйте кнопкой «Изображение» — загруженные файлы сохраняются в хранилище и доступны по путям /uploads/. Рекламный блок внутри статьи добавляется кнопкой «Рекламный блок» (строка ::ad, не более двух на материал). При выделении фрагмента над ним появляется панель быстрых действий. Орфографию подчёркивает браузер: русский и английский словари включаются в его настройках.</p>
      <ImageInsertDialog open={imageDialogOpen} onClose={() => setImageDialogOpen(false)} onInsert={handleImageInsert} />
    </div>
  );
}
