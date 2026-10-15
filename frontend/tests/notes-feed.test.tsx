import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("next/navigation", () => ({ usePathname: () => "/notes" }));
vi.mock("@/lib/api/notes-feed", () => ({ fetchNotesFeed: vi.fn() }));

import { NoteEntry } from "@/components/content/NoteEntry";
import { NotesFeed } from "@/components/content/NotesFeed";
import { fetchNotesFeed } from "@/lib/api/notes-feed";
import type { Note, NotesFeedPage } from "@/lib/api/types";

function note(slug: string, fields: Partial<Note> = {}): Note {
  return {
    slug, title: `Заметка ${slug}`, excerpt: `Короткий текст ${slug}`,
    published_at: "2026-10-15", published_at_time: "2026-10-15T10:25:00Z",
    reading_time: 1, tags: ["AI"], related_article: null,
    content_html: `<p>Полный текст ${slug}</p>`, ...fields,
  };
}

function page(items: Note[], cursor: string | null = null, newest = "head"): NotesFeedPage {
  return { items, next_cursor: cursor, newest_cursor: newest, has_more: cursor !== null };
}

beforeEach(() => {
  vi.mocked(fetchNotesFeed).mockReset();
  window.history.replaceState(null, "", "/notes");
  Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("compact note entries", () => {
  it("shows automatic text, a safe original link, source and publication time without article metadata", async () => {
    const { container } = render(<NoteEntry note={note("auto", {
      source_name: "Источник", source_url: "https://source.example/original",
      excerpt: "А".repeat(301), content_html: '<script>alert(1)</script><p>Model HTML</p>',
    })} />);
    expect(screen.getByText("А".repeat(300))).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.queryByText("Model HTML")).toBeNull();
    const link = screen.getByRole("link", { name: "Подробнее… Заметка auto" });
    expect(link.getAttribute("href")).toBe("https://source.example/original");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(link.getAttribute("rel")).toContain("noreferrer");
    expect(screen.getByText("Источник")).toBeTruthy();
    expect(screen.getByText("15 октября 2026 г., 14:25").getAttribute("datetime")).toBe("2026-10-15T10:25:00Z");
    expect(screen.queryByText(/мин чтения/)).toBeNull();
    expect(screen.queryByText("AI")).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });

  it.each(["javascript:alert(1)", "data:text/html,unsafe", "/relative", "not a URL"])(
    "does not link to an unsafe source %s", (source_url) => {
      render(<NoteEntry note={note("unsafe", { source_name: "Источник", source_url })} />);
      expect(screen.queryByRole("link", { name: /Подробнее/ })).toBeNull();
    },
  );

  it("retains manual Markdown body and related article while suppressing ad markers", () => {
    const body = "Ручная заметка ".repeat(40);
    const { container } = render(<NoteEntry note={note("manual", {
      content_html: `<p><strong>${body}</strong></p><div data-ad-slot="article-inline"></div><p>Продолжение</p>`,
      related_article: { slug: "long-read", title: "Связанная статья" },
      published_at_time: null,
    })} />);
    expect(container.querySelector("strong")?.textContent).toBe(body);
    expect(screen.getByText("Продолжение")).toBeTruthy();
    expect(container.querySelector("[data-ad-slot], aside")).toBeNull();
    expect(screen.getByRole("link", { name: "Связанная статья" }).getAttribute("href")).toBe("/blog/post/long-read");
  });
});

describe("notes feed navigation", () => {
  it("loads older notes by stable cursors, removes duplicates and gives keyboard focus to the first addition", async () => {
    vi.mocked(fetchNotesFeed)
      .mockResolvedValueOnce(page([note("a"), note("b"), note("b")], "older-b"))
      .mockResolvedValueOnce(page([note("c")]));
    render(<NotesFeed initialFeed={page([note("a")], "older-a")} />);
    const more = screen.getByRole("button", { name: "Ещё заметки" });
    more.focus();
    fireEvent.click(more);
    await screen.findByRole("heading", { name: "Заметка b" });
    expect(fetchNotesFeed).toHaveBeenNthCalledWith(1, { limit: 20, before: "older-a" }, expect.any(AbortSignal));
    expect(screen.getAllByRole("article")).toHaveLength(2);
    await waitFor(() => expect(document.activeElement).toBe(document.getElementById("note-b")));
    fireEvent.click(screen.getByRole("button", { name: "Ещё заметки" }));
    await screen.findByRole("heading", { name: "Заметка c" });
    expect(fetchNotesFeed).toHaveBeenNthCalledWith(2, { limit: 20, before: "older-b" }, expect.any(AbortSignal));
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "Ещё заметки" })).toBeNull();
  });

  it("preserves the cursor and readable entries after an error, and retries on demand", async () => {
    vi.mocked(fetchNotesFeed).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(page([note("b")]));
    render(<NotesFeed initialFeed={page([note("a")], "older-a")} compact />);
    fireEvent.click(screen.getByRole("button", { name: "Ещё заметки" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Не удалось"));
    expect(screen.getByRole("heading", { name: "Заметка a" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Повторить загрузку" }));
    await screen.findByRole("heading", { name: "Заметка b" });
    expect(vi.mocked(fetchNotesFeed).mock.calls.map(([params]) => params)).toEqual([
      { limit: 20, before: "older-a" }, { limit: 20, before: "older-a" },
    ]);
  });

  it("exposes a keyboard scroll region and focuses a local anchor without changing routes", () => {
    render(<><NotesFeed initialFeed={page([note("a")])} compact /><a href="/contacts">Контакты</a></>);
    expect(screen.getByRole("region", { name: "Лента заметок" }).tabIndex).toBe(0);
    const link = screen.getByRole("link", { name: "Заметка a" });
    expect(link.getAttribute("href")).toBe("#note-a");
    act(() => {
      window.history.replaceState(null, "", "/notes#note-a");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(document.activeElement).toBe(document.getElementById("note-a"));
    const footerLink = screen.getByRole("link", { name: "Контакты" });
    footerLink.focus();
    expect(document.activeElement).toBe(footerLink);
  });

  it("ends automatic loading after two batches so later page content remains reachable", async () => {
    const observers: { callback: IntersectionObserverCallback; active: boolean; root: Element | Document | null | undefined }[] = [];
    vi.stubGlobal("IntersectionObserver", class {
      observer: (typeof observers)[number];
      constructor(callback: IntersectionObserverCallback, options: IntersectionObserverInit) {
        this.observer = { callback, active: true, root: options.root };
        observers.push(this.observer);
      }
      observe() {}
      disconnect() { this.observer.active = false; }
    });
    vi.mocked(fetchNotesFeed)
      .mockResolvedValueOnce(page([note("b")], "older-b"))
      .mockResolvedValueOnce(page([note("c")], "older-c"));
    render(<NotesFeed initialFeed={page([note("a")], "older-a")} compact />);
    expect(observers[0].root).toBe(screen.getByRole("region", { name: "Лента заметок" }));
    async function intersect(observer: (typeof observers)[number]) {
      await act(async () => observer.callback(
        [{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver,
      ));
    }
    await intersect(observers[0]);
    const second = observers.findLast((observer) => observer.active)!;
    await intersect(second);
    expect(fetchNotesFeed).toHaveBeenCalledTimes(2);
    expect(observers.every((observer) => !observer.active)).toBe(true);
    await intersect(second);
    expect(fetchNotesFeed).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: "Ещё заметки" })).toBeTruthy();
  });

  it("keeps empty content readable and has no axe violations", async () => {
    const { container } = render(<NotesFeed initialFeed={page([])} compact />);
    expect(screen.getByText("Заметки скоро появятся.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("new note notifications", () => {
  it("polls after the newest cursor without moving focus, then refreshes the first page on request", async () => {
    vi.useFakeTimers();
    vi.mocked(fetchNotesFeed)
      .mockResolvedValueOnce(page([note("newest")], null, "new-head"))
      .mockResolvedValueOnce(page([note("newest"), note("between"), note("a")], "new-bottom", "new-head"))
      .mockResolvedValueOnce(page([note("older")]));
    render(<NotesFeed initialFeed={page([note("a")], "older-a")} />);
    const title = screen.getByRole("link", { name: "Заметка a" });
    title.focus();
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(fetchNotesFeed).toHaveBeenNthCalledWith(1, { limit: 1, after: "head" }, expect.any(AbortSignal));
    expect(screen.queryByRole("heading", { name: "Заметка newest" })).toBeNull();
    expect(document.activeElement).toBe(title);
    const notification = screen.getByRole("button", { name: "Появились новые" });
    await act(async () => fireEvent.click(notification));
    expect(fetchNotesFeed).toHaveBeenNthCalledWith(2, { limit: 20 }, expect.any(AbortSignal));
    expect(screen.getByRole("heading", { name: "Заметка between" })).toBeTruthy();
    expect(document.activeElement).toBe(document.getElementById("note-newest"));
    expect(screen.queryByRole("button", { name: "Появились новые" })).toBeNull();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Ещё заметки" })));
    expect(fetchNotesFeed).toHaveBeenNthCalledWith(3, { limit: 20, before: "new-bottom" }, expect.any(AbortSignal));
  });

  it("skips hidden tabs and checks again when the tab becomes visible", async () => {
    vi.useFakeTimers();
    vi.mocked(fetchNotesFeed).mockResolvedValue(page([]));
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    render(<NotesFeed initialFeed={page([note("a")])} />);
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(fetchNotesFeed).not.toHaveBeenCalled();
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    await act(async () => document.dispatchEvent(new Event("visibilitychange")));
    expect(fetchNotesFeed).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Появились новые" })).toBeNull();
  });

  it("aborts pending loads and removes polling when the feed unmounts", async () => {
    vi.useFakeTimers();
    vi.mocked(fetchNotesFeed).mockImplementation(() => new Promise(() => {}));
    const { unmount } = render(<NotesFeed initialFeed={page([note("a")], "older-a")} />);
    fireEvent.click(screen.getByRole("button", { name: "Ещё заметки" }));
    const signal = vi.mocked(fetchNotesFeed).mock.calls[0][1]!;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => vi.advanceTimersByTimeAsync(120_000));
    expect(fetchNotesFeed).toHaveBeenCalledOnce();
  });
});
