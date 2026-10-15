import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({ router: { replace: vi.fn(), refresh: vi.fn() }, fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/admin-api", () => ({ adminFetch: vi.fn(), requireAdmin: vi.fn() }));
vi.mock("@/components/admin/AdminSessionRefresh", () => ({ AdminSessionRefresh: () => null }));

import AdminLayout from "@/app/(admin)/layout";
import NewsNotesPage from "@/app/(admin)/admin/news/notes/page";
import { NewsNoteSettings } from "@/components/admin/news/NewsNoteSettings";
import { NewsNotesQueue } from "@/components/admin/news/NewsNotesQueue";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import type { NewsNote, NewsNoteSettings as NoteSettings } from "@/lib/news-api/types";
import { notePage, noteSettings, queuedNote } from "./news-note-fixtures";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const nativeShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
const nativeClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");

beforeAll(() => {
  // jsdom does not provide the native modal top layer.
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value(this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value(this: HTMLDialogElement) { this.removeAttribute("open"); } });
});
afterAll(() => {
  if (nativeShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", nativeShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  if (nativeClose) Object.defineProperty(HTMLDialogElement.prototype, "close", nativeClose);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});
beforeEach(() => {
  Object.values(router).forEach(fn => fn.mockReset());
  fetchMock.mockReset().mockImplementation(async (url: string, options: RequestInit = {}) => {
    if (url === "/api/admin/news/note-settings") return json(options.body ? { ...noteSettings, ...JSON.parse(String(options.body)) } : noteSettings);
    if (url === `/api/admin/news/note-queue/${queuedNote.note_slug}`) return json({ ...queuedNote, ...JSON.parse(String(options.body)) });
    return json(notePage());
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(requireAdmin).mockReset().mockResolvedValue({ username: "owner" });
  vi.mocked(adminFetch).mockReset().mockImplementation(async path => path === "/news/note-settings" ? noteSettings : notePage());
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function queue(settings: NoteSettings = noteSettings, rows: NewsNote[] = [queuedNote], status: NewsNote["status"] = "queued") {
  return render(<NewsNotesQueue initialSettings={settings} initialQueue={notePage(rows)} status={status} />);
}

function openEditor() {
  const trigger = screen.getByRole("button", { name: `Редактировать заметку: ${queuedNote.title}` });
  fireEvent.click(trigger);
  return { trigger, dialog: screen.getByRole("dialog"), form: screen.getByRole("form", { name: "Редактирование заметки" }) };
}

describe("protected automatic note route", () => {
  it("checks the session before either API read", async () => {
    vi.mocked(requireAdmin).mockRejectedValueOnce(new Error("LOGIN_REQUIRED"));
    await expect(NewsNotesPage({ searchParams: Promise.resolve({}) })).rejects.toThrow("LOGIN_REQUIRED");
    expect(adminFetch).not.toHaveBeenCalled();
  });

  it("renders an accessible queue and validates status and pagination on the server", async () => {
    const { container } = render(<AdminLayout>{await NewsNotesPage({ searchParams: Promise.resolve({ status: "anything", page: "-2" }) })}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/news/note-settings");
    expect(adminFetch).toHaveBeenCalledWith("/news/note-queue?status=queued&page=1&page_size=20");
    expect(within(screen.getByRole("navigation", { name: "Редакционный центр" })).getByRole("link", { name: "Заметки" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: /Опубликованы/ }).getAttribute("href")).toBe("/admin/news/notes?status=published");
    expect(screen.getByRole("link", { name: /первоисточник/ }).getAttribute("rel")).toBe("noopener noreferrer");
    expect(container.textContent).not.toContain("982");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("passes the selected status and page and keeps both in pagination links", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path === "/news/note-settings" ? noteSettings : { ...notePage(), page: 2, total: 45, pages: 3 });
    render(await NewsNotesPage({ searchParams: Promise.resolve({ status: ["excluded", "expired"], page: "2" }) }));
    expect(adminFetch).toHaveBeenCalledWith("/news/note-queue?status=excluded&page=2&page_size=20");
    const pages = within(screen.getByRole("navigation", { name: "Страницы заметок" }));
    expect(pages.getByRole("link", { name: "Назад" }).getAttribute("href")).toBe("/admin/news/notes?status=excluded&page=1");
    expect(pages.getByRole("link", { name: "Вперёд" }).getAttribute("href")).toBe("/admin/news/notes?status=excluded&page=3");
  });
});

describe("automatic note settings", () => {
  it("changes only the publication switch and exposes its pending state", async () => {
    let resolve: (value: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(new Promise<Response>(done => { resolve = done; }));
    const saved = vi.fn();
    render(<NewsNoteSettings settings={noteSettings} onSaved={saved} onBusy={vi.fn()} />);
    const toggle = screen.getByRole("switch", { name: "Автоматическая публикация заметок" });
    fireEvent.click(toggle);
    expect((toggle as HTMLButtonElement).disabled).toBe(true);
    await act(async () => resolve(json({ ...noteSettings, enabled: true })));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/news/note-settings");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "PATCH", credentials: "same-origin", cache: "no-store" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ enabled: true });
    expect(saved).toHaveBeenCalledWith(expect.objectContaining({ enabled: true }));
    expect(screen.getByText("Автоматическая публикация включена.")).toBeTruthy();
  });

  it("saves only bounded interval and age fields", async () => {
    const saved = vi.fn();
    render(<NewsNoteSettings settings={noteSettings} onSaved={saved} onBusy={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Интервал публикации/), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText(/Срок актуальности/), { target: { value: "720" } });
    fireEvent.submit(screen.getByRole("form", { name: "Настройки заметок" }));
    await waitFor(() => expect(saved).toHaveBeenCalledOnce());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ interval_minutes: 10, max_age_hours: 720 });
  });

  it.each([["Интервал публикации", "9"], ["Срок актуальности", "721"]])("rejects an invalid %s before sending", async (label, value) => {
    render(<NewsNoteSettings settings={noteSettings} onSaved={vi.fn()} onBusy={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(new RegExp(label)), { target: { value } });
    fireEvent.submit(screen.getByRole("form", { name: "Настройки заметок" }));
    const error = await screen.findByRole("alert");
    expect(document.activeElement).toBe(error);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves edited settings during a queue refresh", async () => {
    queue();
    fireEvent.change(screen.getByLabelText(/Интервал публикации/), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Обновить очередь" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect((screen.getByLabelText(/Интервал публикации/) as HTMLInputElement).value).toBe("20");
  });
});

describe("note queue actions and editing", () => {
  it("uses the note slug for exclusion and returns focus to the queue heading", async () => {
    fetchMock.mockImplementation(async (url: string, options: RequestInit = {}) => {
      if (options.method === "PATCH") return json({ ...queuedNote, status: "excluded" });
      return json(url.includes("note-settings") ? { ...noteSettings, queued: 0, excluded: 1 } : notePage([]));
    });
    queue();
    fireEvent.click(screen.getByRole("button", { name: `Исключить заметку: ${queuedNote.title}` }));
    await screen.findByText("Заметка исключена из очереди.");
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/admin/news/note-queue/${queuedNote.note_slug}`);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ status: "excluded" });
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Очередь заметок" }));
    await screen.findByRole("link", { name: "Исключены (1)" });
    expect(screen.queryByRole("heading", { name: queuedNote.title })).toBeNull();
  });

  it("restores an excluded note through the same queue contract", async () => {
    queue(noteSettings, [{ ...queuedNote, status: "excluded" }], "excluded");
    fireEvent.click(screen.getByRole("button", { name: `Вернуть в очередь: ${queuedNote.title}` }));
    await screen.findByText("Заметка возвращена в очередь.");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ status: "queued" });
  });

  it("traps modal focus, closes on Escape and restores the trigger", async () => {
    const { container } = queue();
    const { trigger, dialog } = openEditor();
    const first = screen.getByRole("button", { name: "Закрыть редактор заметки" });
    const last = screen.getByRole("button", { name: "Отмена" });
    expect(document.activeElement).toBe(screen.getByLabelText("Заголовок (обязательно)"));
    last.focus(); fireEvent.keyDown(dialog, { key: "Tab" }); expect(document.activeElement).toBe(first);
    first.focus(); fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true }); expect(document.activeElement).toBe(last);
    expect((await axe(container)).violations).toEqual([]);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("saves edited plain text and blocks dismissal during the request", async () => {
    let resolve: (value: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(new Promise<Response>(done => { resolve = done; }));
    queue();
    const { dialog, form } = openEditor();
    fireEvent.change(screen.getByLabelText("Заголовок (обязательно)"), { target: { value: "Уточнённый заголовок" } });
    fireEvent.change(screen.getByLabelText("Текст (обязательно)"), { target: { value: "Короткая проверенная заметка." } });
    fireEvent.submit(form);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByLabelText("Текст (обязательно)").matches(":disabled")).toBe(true);
    await act(async () => resolve(json({ ...queuedNote, title: "Уточнённый заголовок", text: "Короткая проверенная заметка." })));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/admin/news/note-queue/${queuedNote.note_slug}`);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ title: "Уточнённый заголовок", text: "Короткая проверенная заметка." });
    expect(screen.getByText("Заметка сохранена.")).toBeTruthy();
  });

  it("counts spaces and rejects text over 300 characters without a request", async () => {
    queue();
    const { form } = openEditor();
    const input = screen.getByLabelText("Текст (обязательно)");
    expect(input.getAttribute("maxlength")).toBe("300");
    fireEvent.change(input, { target: { value: "а ".repeat(150) + "а" } });
    fireEvent.submit(form);
    expect((await screen.findByRole("alert")).textContent).toContain("включая пробелы");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([401, 403, 409, 422])("keeps the edit available after HTTP %s and focuses the error", async status => {
    fetchMock.mockResolvedValueOnce(json({}, status));
    queue();
    const { form } = openEditor();
    fireEvent.change(screen.getByLabelText("Текст (обязательно)"), { target: { value: "Сохранить этот текст" } });
    fireEvent.submit(form);
    const error = await screen.findByRole("alert");
    await waitFor(() => expect(document.activeElement).toBe(error));
    expect((screen.getByLabelText("Текст (обязательно)") as HTMLTextAreaElement).value).toBe("Сохранить этот текст");
    expect((screen.getByRole("button", { name: "Сохранить заметку" }) as HTMLButtonElement).disabled).toBe(false);
    if (status === 401) expect(router.replace).toHaveBeenCalledWith("/admin/login");
    else expect(router.replace).not.toHaveBeenCalled();
  });

  it("shows an editor link only for an existing published note and rejects unsafe source links", () => {
    const published: NewsNote = { ...queuedNote, status: "published", published_at_time: "2026-10-15T12:00:00Z" };
    const { container } = queue(noteSettings, [published, { ...published, note_slug: "deleted-note", title: "Удалённая заметка", content_id: null, source_url: "javascript:alert(1)" }], "published");
    expect(screen.getAllByRole("link", { name: "Открыть в редакторе" })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Открыть в редакторе" }).getAttribute("href")).toBe("/admin/content/982/edit");
    expect(screen.getAllByRole("link", { name: /первоисточник/ })).toHaveLength(1);
    expect(container.querySelector('[href^="javascript:"]')).toBeNull();
    expect(screen.queryByRole("button", { name: /^Редактировать заметку:/ })).toBeNull();
    expect(screen.getAllByText("Опубликована:", { exact: false })).toHaveLength(2);
  });
});

describe("queue refresh", () => {
  it("keeps the queue after a network failure and retries the read", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    queue();
    fireEvent.click(screen.getByRole("button", { name: "Обновить очередь" }));
    await screen.findByText(/Нет связи с сервером/);
    expect(screen.getByRole("heading", { name: queuedNote.title })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Обновить очередь" }));
    await waitFor(() => expect(screen.queryByText(/Нет связи с сервером/)).toBeNull());
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("polls visible enabled queues and pauses polling while editing or hidden", async () => {
    vi.useFakeTimers();
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    fetchMock.mockImplementation(async (url: string) => json(url.includes("note-settings") ? { ...noteSettings, enabled: true } : notePage()));
    queue({ ...noteSettings, enabled: true });
    await act(async () => { vi.advanceTimersByTime(15000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    visibility.mockReturnValue("hidden");
    await act(async () => { vi.advanceTimersByTime(15000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    visibility.mockReturnValue("visible");
    openEditor();
    await act(async () => { vi.advanceTimersByTime(30000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
