import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({ router: { replace: vi.fn(), refresh: vi.fn() }, fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

import { NewsSourcesList, type NewsSourceRowActivity } from "@/components/admin/news/NewsSourcesList";
import { NewsSourceToggle } from "@/components/admin/news/NewsSourceToggle";
import { sourceDate, sourceScheduleError, sourceToday } from "@/lib/news-api/schedule";
import type { NewsSourceSchedule } from "@/lib/news-api/types";
import { newsSource } from "./news-fixtures";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const nativeShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
const nativeClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");
beforeAll(() => {
  // jsdom has no modal top layer; keep dialog state observable while testing our keyboard handlers.
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value(this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value(this: HTMLDialogElement) { this.removeAttribute("open"); } });
});
afterAll(() => {
  if (nativeShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", nativeShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  if (nativeClose) Object.defineProperty(HTMLDialogElement.prototype, "close", nativeClose);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});
beforeEach(() => { fetchMock.mockReset(); Object.values(router).forEach(fn => fn.mockReset()); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

async function openEditor() {
  fireEvent.click(screen.getByRole("button", { name: /^Изменить расписание:/ }));
  return screen.getByRole("form", { name: `Расписание: ${newsSource.name}` });
}

describe("prepared source controls", () => {
  it("changes a source by slug and keeps focus on the switch after saving", async () => {
    const onSaved = vi.fn();
    fetchMock.mockResolvedValue(json({ ...newsSource, active: true, next_check_at: "2026-10-15T16:00:00Z" }));
    render(<NewsSourcesList sources={[newsSource]} onSaved={onSaved} />);
    const toggle = screen.getByRole("switch");
    toggle.focus();
    fireEvent.click(toggle);
    await screen.findByText("Источник включён.");
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/admin/news/sources/${newsSource.slug}`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "PATCH", credentials: "same-origin", cache: "no-store" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ active: true });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(toggle.querySelector(".news-source-switch-track .news-source-switch-thumb")).toBeTruthy();
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ slug: newsSource.slug, active: true }));
    expect(document.activeElement).toBe(toggle);
    expect(screen.getByText("15.10.2026, 20:00")).toBeTruthy();
  });

  it.each([401, 403, 422, 500])("rolls a failed toggle back after HTTP %s", async status => {
    let resolve: (response: Response) => void = () => {};
    fetchMock.mockReturnValue(new Promise<Response>(done => { resolve = done; }));
    render(<NewsSourceToggle source={newsSource} />);
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect((toggle as HTMLButtonElement).disabled).toBe(true);
    await act(async () => resolve(json({}, status)));
    const error = await screen.findByRole("alert");
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect((toggle as HTMLButtonElement).disabled).toBe(false);
    expect(document.activeElement).toBe(error);
    if (status === 401) expect(router.replace).toHaveBeenCalledWith("/admin/login");
    else expect(router.refresh).not.toHaveBeenCalled();
  });

  it("pauses an active source and removes its next scheduled check", async () => {
    fetchMock.mockResolvedValue(json(newsSource));
    render(<NewsSourcesList sources={[{ ...newsSource, active: true, next_check_at: "2026-10-15T16:00:00Z" }]} />);
    fireEvent.click(screen.getByRole("switch"));
    await screen.findByText("Источник приостановлен.");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ active: false });
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("на паузе")).toBeTruthy();
  });

  it("shows complete long names, descriptions and stable focusable source anchors without configuration fields", async () => {
    const name = "Источник с очень длинным названием ".repeat(7);
    const { container } = render(<main><h1>Источники</h1><NewsSourcesList sources={[{ ...newsSource, name, last_success_at: "2026-10-15T04:00:00Z" }]} /></main>);
    expect(screen.getByText(name.trim())).toBeTruthy();
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getAllByRole("columnheader")).toHaveLength(5);
    expect(screen.getByText(newsSource.description)).toBeTruthy();
    const row = screen.getByRole("row", { name: name.trim() });
    expect(row.id).toBe(newsSource.slug);
    expect(row.getAttribute("tabindex")).toBe("-1");
    expect(screen.getByRole("link", { name: `Последние результаты: ${name.trim()}` }).getAttribute("href")).toBe(`/admin/news/runs?source_slug=${newsSource.slug}`);
    expect(container.textContent).not.toMatch(/RSS|Atom|HTML|CSS|URL|Доверие|Приоритет|поставщик|parser/i);
    expect(container.querySelector('[type="url"], [name="config"], [name="topic_ids"]')).toBeNull();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("offers results after a failed attempt without exposing internal errors", () => {
    const { rerender } = render(<NewsSourcesList sources={[newsSource]} />);
    expect(screen.queryByRole("link", { name: /Последние результаты/ })).toBeNull();
    rerender(<NewsSourcesList sources={[{ ...newsSource, last_error: "parser/private.py: invalid .selector" }]} />);
    expect(screen.getByRole("link", { name: /Последние результаты/ }).getAttribute("href")).toBe(`/admin/news/runs?source_slug=${newsSource.slug}`);
    expect(screen.getByText(/Последняя проверка завершилась с ошибкой/)).toBeTruthy();
    expect(screen.queryByText(/private.py/)).toBeNull();
  });

  it("delegates a compact manual check and disables it during queued or running work", () => {
    const onCollect = vi.fn();
    const activity: NewsSourceRowActivity = { status: "queued", new: 0, updated: 0, unchanged: 0, warnings: 0, error: null };
    const { rerender } = render(<NewsSourcesList sources={[newsSource]} onCollect={onCollect} />);
    const button = screen.getByRole("button", { name: `Проверить: ${newsSource.name}` });
    fireEvent.click(button);
    expect(onCollect).toHaveBeenCalledWith(newsSource);
    expect(fetchMock).not.toHaveBeenCalled();
    for (const status of ["queued", "running"] as const) {
      rerender(<NewsSourcesList sources={[newsSource]} onCollect={onCollect} activityBySource={{ [newsSource.slug]: { ...activity, status } }} />);
      expect((button as HTMLButtonElement).disabled).toBe(true);
      expect(screen.getByText(status === "queued" ? "В очереди" : "Проверяется")).toBeTruthy();
    }
    rerender(<NewsSourcesList sources={[newsSource]} onCollect={onCollect} collectDisabled />);
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it.each([
    ["completed", 3, 1, "Собрано 4 · новых 3"],
    ["completed", 0, 0, "Без новых материалов"],
    ["failed", 0, 0, "Проверка не удалась"],
    ["cancelled", 0, 0, "Проверка отменена"],
  ] as const)("shows compact %s results and the safe API reason as text", (status, count, updated, label) => {
    const activity: NewsSourceRowActivity = { status, new: count, updated, unchanged: 8, warnings: 1, error: 'Источник временно недоступен. <img src=x onerror="alert(1)">' };
    const { container } = render(<NewsSourcesList sources={[newsSource]} activityBySource={{ [newsSource.slug]: activity }} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText("Предупреждений: 1")).toBeTruthy();
    expect(screen.getByText(activity.error!)).toBeTruthy();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("link", { name: /Последние результаты/ })).toBeTruthy();
  });
});

describe("source schedule editor", () => {
  it("saves daily times in order and announces the saved schedule with focus restored", async () => {
    const schedule: NewsSourceSchedule = { mode: "daily", times: ["07:30", "08:00", "20:00"] };
    fetchMock.mockResolvedValue(json({ ...newsSource, schedule }));
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    fireEvent.click(within(form).getByRole("button", { name: "Добавить время" }));
    fireEvent.change(within(form).getByLabelText("Время 3 (обязательно)"), { target: { value: "07:30" } });
    fireEvent.click(within(form).getByRole("button", { name: "Сохранить расписание" }));
    await screen.findByText("Расписание сохранено.");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ schedule });
    expect(screen.getByText("Ежедневно · 07:30, 08:00, 20:00")).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /^Изменить расписание:/ }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps duplicate-time errors in the editor and focuses the explanation", async () => {
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    fireEvent.change(within(form).getByLabelText("Время 2 (обязательно)"), { target: { value: "08:00" } });
    fireEvent.submit(form);
    const error = await screen.findByRole("alert");
    expect(error.textContent).toBe("Времена проверки должны различаться.");
    expect(document.activeElement).toBe(error);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(form.closest("dialog")?.open).toBe(true);
  });

  it("saves an interval anchored to its first calendar date in Samara", async () => {
    const schedule: NewsSourceSchedule = { mode: "interval_days", times: ["08:00", "20:00"], every_days: 3, start_date: "2026-10-15" };
    fetchMock.mockResolvedValue(json({ ...newsSource, schedule }));
    const { container } = render(<main><h1>Источники</h1><NewsSourcesList sources={[newsSource]} /></main>);
    const form = await openEditor();
    fireEvent.change(within(form).getByLabelText("Как часто проверять"), { target: { value: "interval_days" } });
    fireEvent.change(within(form).getByLabelText("Первый день расписания (обязательно)"), { target: { value: "2026-10-15" } });
    expect(within(form).getByText(/начиная с этой даты/)).toBeTruthy();
    expect((await axe(container)).violations).toEqual([]);
    fireEvent.click(within(form).getByRole("button", { name: "Сохранить расписание" }));
    await screen.findByText("Расписание сохранено.");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ schedule });
    expect(screen.getByText("Каждые 3 дн. с 15.10.2026 · 08:00, 20:00")).toBeTruthy();
  });

  it("requires selected weekdays and saves their Monday-based values", async () => {
    const schedule: NewsSourceSchedule = { mode: "weekly", times: ["08:00", "20:00"], weekdays: [0, 3] };
    fetchMock.mockResolvedValue(json({ ...newsSource, schedule }));
    const { container } = render(<main><h1>Источники</h1><NewsSourcesList sources={[newsSource]} /></main>);
    const form = await openEditor();
    fireEvent.change(within(form).getByLabelText("Как часто проверять"), { target: { value: "weekly" } });
    fireEvent.click(within(form).getByLabelText("Понедельник"));
    fireEvent.submit(form);
    expect((await screen.findByRole("alert")).textContent).toContain("хотя бы один день");
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(within(form).getByLabelText("Четверг"));
    fireEvent.click(within(form).getByLabelText("Понедельник"));
    expect((await axe(container)).violations).toEqual([]);
    fireEvent.submit(form);
    await screen.findByText("Расписание сохранено.");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ schedule });
    expect(screen.getByText("По дням недели: пн, чт · 08:00, 20:00")).toBeTruthy();
  });

  it("preserves the current schedule and edited values after a failed save", async () => {
    fetchMock.mockResolvedValue(json({}, 500));
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    fireEvent.change(within(form).getByLabelText("Время 1 (обязательно)"), { target: { value: "06:00" } });
    fireEvent.submit(form);
    await screen.findByRole("alert");
    expect(screen.getByText("Ежедневно · 08:00, 20:00")).toBeTruthy();
    expect((within(form).getByLabelText("Время 1 (обязательно)") as HTMLInputElement).value).toBe("06:00");
    expect(form.closest("dialog")?.open).toBe(true);
    expect(router.refresh).not.toHaveBeenCalled();
  });

  it.each(["cancel", "close", "escape", "backdrop"])("discards edits after %s and restores the trigger focus", async action => {
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    fireEvent.change(within(form).getByLabelText("Время 1 (обязательно)"), { target: { value: "06:00" } });
    const dialog = screen.getByRole("dialog");
    if (action === "cancel") fireEvent.click(within(form).getByRole("button", { name: "Отмена" }));
    else if (action === "close") fireEvent.click(within(dialog).getByRole("button", { name: "Закрыть расписание" }));
    else if (action === "escape") fireEvent.keyDown(dialog, { key: "Escape" });
    else fireEvent.click(dialog);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /^Изменить расписание:/ }));
    const reopened = await openEditor();
    expect((within(reopened).getByLabelText("Время 1 (обязательно)") as HTMLInputElement).value).toBe("08:00");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("moves focus into the dialog and wraps Tab and Shift+Tab within its controls", async () => {
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    const dialog = screen.getByRole("dialog", { name: `Расписание: ${newsSource.name}` });
    expect(document.activeElement).toBe(within(form).getByLabelText("Как часто проверять"));
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(document.body.style.overflow).toBe("hidden");
    const first = within(dialog).getByRole("button", { name: "Закрыть расписание" });
    const last = within(dialog).getByRole("button", { name: "Отмена" });
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(last, { key: "Escape" });
    expect(document.body.style.overflow).toBe("");
  });

  it("blocks duplicate submission and all dismissal paths while a save is pending", async () => {
    let resolve: (response: Response) => void = () => {};
    fetchMock.mockReturnValue(new Promise<Response>(done => { resolve = done; }));
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    const dialog = screen.getByRole("dialog");
    const close = within(dialog).getByRole("button", { name: "Закрыть расписание" });
    const cancel = within(dialog).getByRole("button", { name: "Отмена" });
    fireEvent.submit(form);
    fireEvent.submit(form);
    fireEvent.click(close);
    fireEvent.click(cancel);
    fireEvent.click(dialog);
    fireEvent.keyDown(dialog, { key: "Escape" });
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(form.getAttribute("aria-busy")).toBe("true");
    expect((close as HTMLButtonElement).disabled).toBe(true);
    expect((within(form).getByLabelText("Как часто проверять") as HTMLSelectElement).matches(":disabled")).toBe(true);
    expect(screen.getByRole("dialog")).toBe(dialog);
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(dialog);
    await act(async () => resolve(json(newsSource)));
    await screen.findByText("Расписание сохранено.");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("displays UTC instants and the current calendar day in the fixed Samara timezone", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-14T21:30:00Z"));
    expect(sourceToday()).toBe("2026-10-15");
    expect(sourceDate("2026-10-14T21:30:00Z")).toBe("15.10.2026, 01:30");
  });

  it.each([
    { mode: "daily", times: [] }, { mode: "daily", times: ["24:00"] },
    { mode: "daily", times: Array.from({ length: 13 }, (_, index) => `${String(index).padStart(2, "0")}:00`) },
    { mode: "interval_days", times: ["08:00"], every_days: 0, start_date: "2026-10-15" },
    { mode: "interval_days", times: ["08:00"], every_days: 366, start_date: "2026-10-15" },
    { mode: "interval_days", times: ["08:00"], every_days: 1.5, start_date: "2026-10-15" },
    { mode: "interval_days", times: ["08:00"], every_days: 3, start_date: "2026-02-30" },
  ] satisfies NewsSourceSchedule[])("rejects invalid schedule %j before submission", schedule => {
    expect(sourceScheduleError(schedule)).not.toBe("");
  });
});
