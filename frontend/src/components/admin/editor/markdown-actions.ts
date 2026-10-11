export type MarkdownAction = "bold" | "italic" | "heading2" | "heading3" | "quote" | "link" | "listBullet" | "listNumber" | "code";

export interface MarkdownEditResult {
  text: string;
  selectionStart: number;
  selectionEnd: number;
}

interface Wrapper {
  before: string;
  after: string;
  placeholder: string;
}

const wrappers: Record<"bold" | "italic" | "codeBlock" | "codeInline", Wrapper> = {
  bold: { before: "**", after: "**", placeholder: "жирный текст" },
  italic: { before: "*", after: "*", placeholder: "курсив" },
  codeBlock: { before: "```\n", after: "\n```", placeholder: "код" },
  codeInline: { before: "`", after: "`", placeholder: "код" },
};

function wrapSelection(source: string, start: number, end: number, wrapper: Wrapper): MarkdownEditResult {
  const selected = source.slice(start, end) || wrapper.placeholder;
  const before = source.slice(0, start);
  const after = source.slice(end);
  if (before.endsWith(wrapper.before) && after.startsWith(wrapper.after)) {
    return {
      text: before.slice(0, before.length - wrapper.before.length) + selected + after.slice(wrapper.after.length),
      selectionStart: start - wrapper.before.length,
      selectionEnd: end - wrapper.before.length,
    };
  }
  return {
    text: before + wrapper.before + selected + wrapper.after + after,
    selectionStart: start + wrapper.before.length,
    selectionEnd: start + wrapper.before.length + selected.length,
  };
}

function lineBounds(source: string, start: number, end: number): { from: number; to: number } {
  const from = source.lastIndexOf("\n", start - 1) + 1;
  const nextBreak = source.indexOf("\n", end);
  return { from, to: nextBreak === -1 ? source.length : nextBreak };
}

function transformLines(source: string, start: number, end: number, transform: (line: string, index: number) => string): MarkdownEditResult {
  const { from, to } = lineBounds(source, start, end);
  const block = source.slice(from, to);
  const lines = block.split("\n");
  const updated = lines.map((line, index) => (line.trim() ? transform(line, index) : line));
  const text = updated.join("\n");
  return { text: source.slice(0, from) + text + source.slice(to), selectionStart: from, selectionEnd: from + text.length };
}

function toggleLinePrefix(source: string, start: number, end: number, add: string, own: RegExp, alternatives: RegExp[] = []): MarkdownEditResult {
  const { from, to } = lineBounds(source, start, end);
  const block = source.slice(from, to);
  const lines = block.split("\n").filter((line) => line.trim());
  if (!lines.length) {
    return { text: source, selectionStart: start, selectionEnd: end };
  }
  if (lines.every((line) => own.test(line))) {
    return transformLines(source, start, end, (line) => line.replace(own, ""));
  }
  return transformLines(source, start, end, (line) => {
    if (own.test(line)) return line;
    for (const alternative of alternatives) {
      if (alternative.test(line)) return add + line.replace(alternative, "");
    }
    return add + line;
  });
}

export function applyMarkdownAction(source: string, start: number, end: number, action: MarkdownAction): MarkdownEditResult {
  switch (action) {
    case "bold":
      return wrapSelection(source, start, end, wrappers.bold);
    case "italic":
      return wrapSelection(source, start, end, wrappers.italic);
    case "code":
      return wrapSelection(source, start, end, source.slice(start, end).includes("\n") ? wrappers.codeBlock : wrappers.codeInline);
    case "heading2":
      return toggleLinePrefix(source, start, end, "## ", /^##(?!#)[ \t]+/, [/^#{3,6}[ \t]+/]);
    case "heading3":
      return toggleLinePrefix(source, start, end, "### ", /^###[ \t]+/, [/^##(?!#)[ \t]+/, /^#{4,6}[ \t]+/]);
    case "quote":
      return toggleLinePrefix(source, start, end, "> ", /^>[ \t]+/);
    case "listBullet":
      return toggleLinePrefix(source, start, end, "- ", /^[-*+][ \t]+/);
    case "listNumber":
      return transformLines(source, start, end, (line, index) => `${index + 1}. ${line.replace(/^\d+\.\s+/, "")}`);
    case "link": {
      const selected = source.slice(start, end) || "текст ссылки";
      const insert = `[${selected}](https://)`;
      return {
        text: source.slice(0, start) + insert + source.slice(end),
        selectionStart: start + selected.length + 3,
        selectionEnd: start + insert.length - 1,
      };
    }
  }
}

/** Replaces the selection with a standalone block, keeping it on its own lines so it never glues onto a non-empty line. */
export function insertBlockAtCursor(source: string, from: number, to: number, block: string): MarkdownEditResult {
  const before = source.slice(0, from);
  const after = source.slice(to);
  let prefix = "";
  if (before.length) {
    if (before.endsWith("\n\n")) prefix = "";
    else if (before.endsWith("\n")) prefix = "\n";
    else prefix = "\n\n";
  }
  let suffix = "";
  if (after.length) {
    if (after.startsWith("\n\n")) suffix = "";
    else if (after.startsWith("\n")) suffix = "\n";
    else suffix = "\n\n";
  }
  const inserted = before + prefix + block;
  return { text: inserted + suffix + after, selectionStart: inserted.length, selectionEnd: inserted.length };
}
