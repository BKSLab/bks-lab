import { render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/notes",
  notFound: vi.fn(() => { throw new Error("NEXT_NOT_FOUND"); }),
  permanentRedirect: vi.fn(() => { throw new Error("NEXT_REDIRECT"); }),
}));
vi.mock("@/lib/api", () => ({ getNotes: vi.fn(), getNotesFeed: vi.fn() }));

import { NotesPageContent, notesMetadata } from "@/components/content/NotesPageContent";
import PaginatedNotesPage, { generateStaticParams } from "@/app/(public)/notes/page/[page]/page";
import { getNotes, getNotesFeed } from "@/lib/api";
import type { Note, Paged } from "@/lib/api/types";
import { NOTE_PAGE_SIZE } from "@/lib/content";

const note: Note = {
  slug: "server-note", title: "Заметка в HTML", excerpt: "Короткий текст", published_at: "2026-10-15",
  reading_time: 1, tags: [], related_article: null, content_html: "<p>Полный серверный текст.</p>",
};
function paged(page = 1): Paged<Note> {
  return { items: [note], total: 41, page, page_size: 20, pages: 3 };
}

beforeEach(() => {
  vi.mocked(getNotes).mockReset().mockResolvedValue(paged());
  vi.mocked(getNotesFeed).mockReset().mockResolvedValue({ items: [note], next_cursor: "older", newest_cursor: "head", has_more: true });
});

describe("server rendered notes routes", () => {
  it("includes initial notes and real archive links in HTML before JavaScript runs", async () => {
    const html = renderToStaticMarkup(await NotesPageContent({}));
    const doc = new DOMParser().parseFromString(html, "text/html");
    expect(doc.querySelectorAll("h1")).toHaveLength(1);
    expect(doc.getElementById("note-server-note")?.textContent).toContain("Полный серверный текст.");
    expect(doc.querySelector('a[href="/notes/page/2"]')).not.toBeNull();
    expect(doc.querySelector('a[href="/notes/page/3"]')).not.toBeNull();
    expect(vi.mocked(getNotesFeed)).toHaveBeenCalledWith({ limit: 20 });
    expect(vi.mocked(getNotes)).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(NOTE_PAGE_SIZE).toBe(20);
  });

  it("renders archive pages with working previous/next URLs and content anchors", async () => {
    vi.mocked(getNotes).mockResolvedValue(paged(2));
    render(await NotesPageContent({ page: 2 }));
    expect(getNotesFeed).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Страница 2");
    expect(screen.getByRole("link", { name: "Назад" }).getAttribute("href")).toBe("/notes");
    expect(screen.getByRole("link", { name: "Далее" }).getAttribute("href")).toBe("/notes/page/3");
    expect(screen.getByRole("link", { name: "Заметка в HTML" }).getAttribute("href")).toBe("#note-server-note");
    expect(screen.queryByRole("button", { name: "Ещё заметки" })).toBeNull();
    expect(notesMetadata(2).alternates?.canonical).toBe("/notes/page/2");
  });

  it("rejects missing archive pages and redirects the duplicate first page", async () => {
    await expect(NotesPageContent({ page: 4 })).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(PaginatedNotesPage({ params: Promise.resolve({ page: "1" }) })).rejects.toThrow("NEXT_REDIRECT");
    await expect(PaginatedNotesPage({ params: Promise.resolve({ page: "invalid" }) })).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(generateStaticParams()).resolves.toEqual([{ page: "2" }, { page: "3" }]);
  });
});
