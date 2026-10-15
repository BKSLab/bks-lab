import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({ router: { replace: vi.fn(), refresh: vi.fn() }, fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

import { NewsSourcesList } from "@/components/admin/news/NewsSourcesList";
import { NewsSourceToggle } from "@/components/admin/news/NewsSourceToggle";
import { sourceDate, sourceScheduleError, sourceToday } from "@/lib/news-api/schedule";
import type { NewsSourceSchedule } from "@/lib/news-api/types";
import { newsSource } from "./news-fixtures";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
beforeEach(() => { fetchMock.mockReset(); Object.values(router).forEach(fn => fn.mockReset()); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

async function openEditor() {
  fireEvent.click(screen.getByText("Изменить расписание", { selector: "summary" }));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  return screen.getByRole("form", { name: `Расписание: ${newsSource.name}` });
}

describe("prepared source controls", () => {
  it("changes a source by slug and keeps focus on the switch after saving", async () => {
    fetchMock.mockResolvedValue(json({ ...newsSource, active: true, next_check_at: "2026-10-15T16:00:00Z" }));
    render(<NewsSourcesList sources={[newsSource]} />);
    const toggle = screen.getByRole("switch");
    toggle.focus();
    fireEvent.click(toggle);
    await screen.findByText("Источник включён.");
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/admin/news/sources/${newsSource.slug}`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "PATCH", credentials: "same-origin", cache: "no-store" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ active: true });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
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
    expect(screen.getByText("Следующая проверка: на паузе")).toBeTruthy();
  });

  it("shows complete long names, descriptions and stable focusable source anchors without configuration fields", async () => {
    const name = "Источник с очень длинным названием ".repeat(7);
    const { container } = render(<main><h1>Источники</h1><NewsSourcesList sources={[{ ...newsSource, name, last_success_at: "2026-10-15T04:00:00Z" }]} /></main>);
    expect(screen.getByRole("heading", { name: name.trim() })).toBeTruthy();
    expect(screen.getByText(newsSource.description)).toBeTruthy();
    const row = screen.getByRole("article");
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
    expect(document.activeElement).toBe(screen.getByText("Изменить расписание", { selector: "summary" }));
    expect(form.closest("details")?.open).toBe(false);
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
    expect(form.closest("details")?.open).toBe(true);
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
    expect(form.closest("details")?.open).toBe(true);
    expect(router.refresh).not.toHaveBeenCalled();
  });

  it("discards cancelled edits when reopened", async () => {
    render(<NewsSourcesList sources={[newsSource]} />);
    const form = await openEditor();
    fireEvent.change(within(form).getByLabelText("Время 1 (обязательно)"), { target: { value: "06:00" } });
    fireEvent.click(within(form).getByRole("button", { name: "Отмена" }));
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
    await openEditor();
    expect((within(form).getByLabelText("Время 1 (обязательно)") as HTMLInputElement).value).toBe("08:00");
    expect(fetchMock).not.toHaveBeenCalled();
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
