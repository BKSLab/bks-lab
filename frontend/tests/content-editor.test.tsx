import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({
  router: { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() },
  fetchMock: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

import { applyMarkdownAction, insertBlockAtCursor } from "@/components/admin/editor/markdown-actions";
import { MarkdownEditor } from "@/components/admin/editor/MarkdownEditor";
import { SelectionBubble } from "@/components/admin/editor/SelectionBubble";
import { EditorPreview } from "@/components/admin/editor/EditorPreview";
import { RevisionList } from "@/components/admin/editor/RevisionList";
import { ConfirmDialog } from "@/components/admin/editor/ConfirmDialog";
import { ContentEditorForm } from "@/components/admin/editor/ContentEditorForm";
import type { AdminContentDetail } from "@/lib/admin-api/types";

beforeEach(() => {
  fetchMock.mockReset();
  Object.values(router).forEach((fn) => fn.mockReset());
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe("markdown actions", () => {
  it("wraps the selection in bold markers and unwraps it back", () => {
    const result = applyMarkdownAction("привет мир", 0, 6, "bold");
    expect(result.text).toBe("**привет** мир");
    expect(result.selectionStart).toBe(2);
    expect(result.selectionEnd).toBe(8);
    const undone = applyMarkdownAction(result.text, result.selectionStart, result.selectionEnd, "bold");
    expect(undone.text).toBe("привет мир");
  });

  it("inserts a placeholder for italic when nothing is selected", () => {
    const result = applyMarkdownAction("текст", 5, 5, "italic");
    expect(result.text).toBe("текст*курсив*");
  });

  it("toggles a second-level heading on the current line", () => {
    const prefixed = applyMarkdownAction("заголовок\nабзац", 2, 5, "heading2");
    expect(prefixed.text).toBe("## заголовок\nабзац");
    const removed = applyMarkdownAction(prefixed.text, 4, 7, "heading2");
    expect(removed.text).toBe("заголовок\nабзац");
  });

  it("replaces a third-level heading when applying a second-level one", () => {
    const result = applyMarkdownAction("### заголовок", 5, 8, "heading2");
    expect(result.text).toBe("## заголовок");
  });

  it("quotes every non-empty line of the selection block", () => {
    const result = applyMarkdownAction("один\nдва\n\nтри", 0, 11, "quote");
    expect(result.text).toBe("> один\n> два\n\n> три");
  });

  it("numbers lines of the selection block", () => {
    const result = applyMarkdownAction("один\nдва", 0, 7, "listNumber");
    expect(result.text).toBe("1. один\n2. два");
  });

  it("inserts a link with the URL part selected", () => {
    const result = applyMarkdownAction("читайте далее", 8, 13, "link");
    expect(result.text).toBe("читайте [далее](https://)");
    expect(result.text.slice(result.selectionStart, result.selectionEnd)).toBe("https://");
  });

  it("uses a fenced block for multiline code", () => {
    const result = applyMarkdownAction("первая строка\nвторая строка", 0, 27, "code");
    expect(result.text).toBe("```\nпервая строка\nвторая строка\n```");
  });
});

describe("insertBlockAtCursor", () => {
  it("inserts the block into an empty document", () => {
    const result = insertBlockAtCursor("", 0, 0, "::ad");
    expect(result.text).toBe("::ad");
    expect(result.selectionStart).toBe(4);
    expect(result.selectionEnd).toBe(4);
  });

  it("keeps the block on its own lines at the start of a document line", () => {
    const result = insertBlockAtCursor("первый абзац\nвторой абзац", 13, 13, "::ad");
    expect(result.text).toBe("первый абзац\n\n::ad\n\nвторой абзац");
    expect(result.selectionStart).toBe(result.text.indexOf("::ad") + 4);
  });

  it("never glues the block onto a non-empty line inside a paragraph", () => {
    const result = insertBlockAtCursor("абзац текста", 3, 3, "::ad");
    expect(result.text).toBe("абз\n\n::ad\n\nац текста");
    expect(result.text.split("\n")).toContain("::ad");
  });

  it("replaces the selection with the block", () => {
    const result = insertBlockAtCursor("один два три", 5, 8, "::ad");
    expect(result.text).toBe("один \n\n::ad\n\n три");
    expect(result.selectionStart).toBe(result.text.indexOf("::ad") + 4);
  });
});

describe("MarkdownEditor toolbar", () => {
  it("inserts markup around the cursor via toolbar buttons", async () => {
    const onChange = vi.fn();
    const { container } = render(<MarkdownEditor value="привет" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Жирный" }));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(onChange.mock.calls.at(-1)![0]).toContain("**");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("labels the editing surface for screen readers", () => {
    render(<MarkdownEditor value="" onChange={() => {}} />);
    const surface = document.querySelector(".cm-content");
    expect(surface).toBeTruthy();
    const labelId = surface!.getAttribute("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId!)!.textContent).toContain("Markdown");
    expect(surface!.getAttribute("spellcheck")).toBe("true");
  });

  it("inserts a standalone ::ad paragraph via the toolbar button", async () => {
    const onChange = vi.fn();
    render(<MarkdownEditor value="абзац" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Рекламный блок" }));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const text = onChange.mock.calls.at(-1)![0] as string;
    expect(text.split("\n")).toContain("::ad");
    expect(text.replace(/\n/g, "")).toMatch(/^(абзац::ad|::adабзац)$/);
  });
});

describe("SelectionBubble", () => {
  it("renders labelled icon actions and forwards the chosen action", async () => {
    const onAction = vi.fn();
    const { container } = render(<SelectionBubble top={10} left={40} onAction={onAction} />);
    const toolbar = screen.getByRole("toolbar", { name: "Действия с выделенным фрагментом" });
    for (const name of ["Жирный", "Курсив", "Ссылка", "Цитата", "Код"]) {
      expect(within(toolbar).getByRole("button", { name })).toBeTruthy();
    }
    fireEvent.click(within(toolbar).getByRole("button", { name: "Жирный" }));
    expect(onAction).toHaveBeenCalledWith("bold");
    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("EditorPreview", () => {
  it("debounces the markdown and requests the preview endpoint", async () => {
    fetchMock.mockResolvedValue(json({ html: "<h2>Заголовок</h2><p>Текст</p>" }));
    const { container } = render(<EditorPreview markdown="# Заголовок" />);
    expect(fetchMock).not.toHaveBeenCalled();
    await sleep(150);
    expect(fetchMock).not.toHaveBeenCalled();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/content/preview");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ content_markdown: "# Заголовок" });
    await waitFor(() => expect(container.querySelector(".prose-content h2")?.textContent).toBe("Заголовок"));
  });

  it("skips the request while the markdown is empty", async () => {
    render(<EditorPreview markdown="   " />);
    await sleep(600);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("ConfirmDialog", () => {
  it("traps focus, confirms on the action button and cancels on Escape", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const { container } = render(
      <div>
        <button type="button">За диалогом</button>
        <ConfirmDialog open title="Точно откатить?" description="История сохранится." onConfirm={onConfirm} onCancel={onCancel} />
      </div>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Отмена" }));
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("RevisionList", () => {
  const revisions = [
    { revision_no: 2, word_count: 120, created_at: "2026-10-08T10:00:00Z" },
    { revision_no: 1, word_count: 100, created_at: "2026-10-01T10:00:00Z" },
  ];
  const item: AdminContentDetail = {
    id: 7, type: "article", slug: "demo", title: "Демо", category: "development", tags: [], published_at: "2026-10-01",
    status: "active", word_count: 120, views_30d: 0, excerpt: null, cover_image: null, seo_title: null, seo_description: null,
    og_image: null, related_slug: null, featured: false, sort_order: null, reading_time: null, content_markdown: "текст",
    created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-08T10:00:00Z", views_timeseries_30d: [],
  };

  it("lists revisions and restores a version after confirmation", async () => {
    fetchMock
      .mockResolvedValueOnce(json(revisions))
      .mockResolvedValueOnce(json(item));
    render(<RevisionList itemId={7} />);
    expect(await screen.findByText("Версия 2")).toBeTruthy();
    expect(screen.getByText(/слов: 100/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Откатить" })[1]);
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("версии 1");
    fireEvent.click(within(dialog).getByRole("button", { name: "Откатить" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/content/7/revisions/1/restore");
    expect(fetchMock.mock.calls[1][1].method).toBe("POST");
    expect(((await screen.findByRole("status")) as HTMLElement).textContent).toContain("Версия 1 восстановлена");
  });
});

describe("ContentEditorForm", () => {
  function openSettings() {
    fireEvent.click(screen.getByRole("tab", { name: "Настройки" }));
  }

  function fillArticle() {
    openSettings();
    fireEvent.change(screen.getByLabelText("Адрес (slug), обязательно"), { target: { value: "new-post" } });
    fireEvent.change(screen.getByLabelText("Заголовок, обязательно"), { target: { value: "Новая статья" } });
    fireEvent.change(screen.getByLabelText("Категория, обязательно"), { target: { value: "development" } });
    fireEvent.change(screen.getByLabelText("Дата публикации, обязательно"), { target: { value: "2026-10-21" } });
    fireEvent.change(screen.getByLabelText("Аннотация, обязательно"), { target: { value: "Коротко о статье" } });
    fireEvent.change(screen.getByLabelText("Обложка, обязательно"), { target: { value: "/images/articles/new-post.webp" } });
    fireEvent.change(screen.getByLabelText("Теги"), { target: { value: "FastAPI, PostgreSQL" } });
  }

  it("creates a draft article with a POST request", async () => {
    fetchMock.mockResolvedValue(json({ id: 42 }, 201));
    render(<ContentEditorForm mode="create" type="article" />);
    fillArticle();
    fireEvent.click(screen.getByRole("button", { name: "Создать статью" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/admin/content/42/edit"));
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/admin/content");
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("same-origin");
    expect(JSON.parse(options.body)).toEqual({
      type: "article", slug: "new-post", title: "Новая статья", draft: true,
      category: "development", published_at: "2026-10-21", excerpt: "Коротко о статье",
      cover_image: "/images/articles/new-post.webp", tags: ["FastAPI", "PostgreSQL"],
      seo_title: null, seo_description: null, og_image: null, reading_time: null,
      content_markdown: "",
    });
  });

  it("focuses a textual error and blocks submission when required fields are missing", async () => {
    render(<ContentEditorForm mode="create" type="note" />);
    fireEvent.click(screen.getByRole("button", { name: "Создать заметку" }));
    const error = await screen.findByRole("alert");
    expect(error.textContent).toContain("Заполните заголовок");
    expect(document.activeElement).toBe(error);
    expect(screen.getByRole("tab", { name: "Настройки" }).getAttribute("aria-selected")).toBe("true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an invalid slug before sending anything", async () => {
    render(<ContentEditorForm mode="create" type="article" />);
    openSettings();
    fireEvent.change(screen.getByLabelText("Заголовок, обязательно"), { target: { value: "Заголовок" } });
    fireEvent.change(screen.getByLabelText("Адрес (slug), обязательно"), { target: { value: "Bad Slug" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать статью" }));
    expect((await screen.findByRole("alert")).textContent).toContain("slug");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("mounts the preview only after the preview tab is opened", async () => {
    const item: AdminContentDetail = {
      id: 9, type: "note", slug: "note-9", title: "Заметка", category: null, tags: [], published_at: "2026-10-01",
      status: "draft", word_count: 10, views_30d: 0, excerpt: null, cover_image: null, seo_title: null, seo_description: null,
      og_image: null, related_slug: null, featured: false, sort_order: null, reading_time: null, content_markdown: "тело заметки",
      created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z", views_timeseries_30d: [],
    };
    fetchMock.mockResolvedValue(json({ html: "<p>тело заметки</p>" }));
    render(<ContentEditorForm mode="edit" item={item} />);
    await sleep(600);
    expect(screen.queryByRole("region", { name: "Предпросмотр материала" })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: "Предпросмотр" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/content/preview");
    expect(await screen.findByRole("region", { name: "Предпросмотр материала" })).toBeTruthy();
  });

  it("sends a PATCH without slug or type when editing", async () => {
    const item: AdminContentDetail = {
      id: 5, type: "note", slug: "note-1", title: "Заметка", category: null, tags: ["x"], published_at: "2026-10-01",
      status: "draft", word_count: 10, views_30d: 0, excerpt: null, cover_image: null, seo_title: null, seo_description: null,
      og_image: null, related_slug: null, featured: false, sort_order: null, reading_time: null, content_markdown: "тело",
      created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z", views_timeseries_30d: [],
    };
    fetchMock.mockResolvedValue(json(item));
    render(<ContentEditorForm mode="edit" item={item} />);
    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/admin/content/5");
    expect(options.method).toBe("PATCH");
    const body = JSON.parse(options.body);
    expect(body).not.toHaveProperty("slug");
    expect(body).not.toHaveProperty("type");
    expect(body).toMatchObject({ title: "Заметка", published_at: "2026-10-01", related_slug: null, content_markdown: "тело" });
  });
});
