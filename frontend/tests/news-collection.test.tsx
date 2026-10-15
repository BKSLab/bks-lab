import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { NewsCollectionStatus } from "@/lib/news-api/types";

const { router, fetchMock } = vi.hoisted(() => ({ router: { replace: vi.fn(), refresh: vi.fn() }, fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

import { NewsCollectionWorkspace } from "@/components/admin/news/NewsCollectionWorkspace";
import { NewsCollectionProgress } from "@/components/admin/news/NewsCollectionProgress";
import { newsCollectJob, newsCollectionStatus, newsSource } from "./news-fixtures";

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
function running(): NewsCollectionStatus {
  return {
    ...structuredClone(newsCollectionStatus), busy: true, active_jobs: 1,
    job: { slug: newsCollectJob.slug, status: "running", source_slug: null, source_name: null, created_at: newsCollectJob.created_at, started_at: newsCollectJob.started_at, completed_at: null, error: null },
    collection: { ...newsCollectionStatus.collection, sources_total: 2, sources_running: 1, sources_queued: 1 },
    sources: [{ source_slug: newsSource.slug, source_name: newsSource.name, status: "running", new: 0, updated: 0, unchanged: 0, skipped: 0, warnings: 0, error: null, analysis: structuredClone(newsCollectionStatus.analysis) }],
  };
}
function analyzed(): NewsCollectionStatus {
  const value = running();
  value.busy = false; value.active_jobs = 0;
  value.job = { ...value.job!, status: "completed", completed_at: newsCollectJob.completed_at };
  value.collection = { ...value.collection, sources_total: 1, sources_done: 1, sources_completed: 1, sources_running: 0, sources_queued: 0, new: 3 };
  value.analysis = { ...value.analysis, total: 3, completed: 3 };
  value.sources[0] = { ...value.sources[0], status: "completed", new: 3, analysis: value.analysis };
  return value;
}

beforeEach(() => {
  fetchMock.mockReset().mockImplementation(async () => json(newsCollectionStatus));
  Object.values(router).forEach(mock => mock.mockReset());
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(document, "hidden", "get").mockReturnValue(false);
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("durable collection workspace", () => {
  it("restores server progress and source state without starting a collection", async () => {
    const initial = running(); fetchMock.mockResolvedValue(json(initial));
    const { container } = render(<main><h1>Источники</h1><NewsCollectionWorkspace initialSources={[newsSource]} initialStatus={initial} /></main>);
    expect(screen.getByText("Проверяем источники")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Проверенные источники" }).getAttribute("max")).toBe("2");
    expect(within(screen.getByRole("row", { name: newsSource.name })).getByText("Проверяется")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Проверить все включённые" }) as HTMLButtonElement).disabled).toBe(true);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/news/collection-status");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "GET", cache: "no-store", credentials: "same-origin" });
    expect((await axe(container)).violations).toEqual([]);
  });

  it("shows collection and model analysis as separate stages then finishes", async () => {
    vi.useFakeTimers();
    let value = running(); fetchMock.mockImplementation(async () => json(value));
    render(<NewsCollectionWorkspace initialSources={[newsSource]} initialStatus={value} />);
    await act(async () => {});
    value = analyzed(); value.busy = true; value.analysis.completed = 1; value.analysis.running = 1; value.analysis.queued = 1;
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(screen.getByText("Сбор завершён, идёт анализ")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Проверенные источники" }).getAttribute("value")).toBe("1");
    expect(screen.getByRole("progressbar", { name: "Готовые анализы" }).getAttribute("value")).toBe("1");
    expect(screen.getByText("Собрано 3 · новых 3")).toBeTruthy();
    value = analyzed();
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(screen.getByText("Проверка завершена")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Готовые анализы" }).getAttribute("value")).toBe("3");
    expect(router.refresh).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: "Открыть отчёт" }).getAttribute("href")).toBe(`/admin/news/jobs/${newsCollectJob.slug}`);
  });

  it.each(["all", "one"])("starts %s scope once and follows its accepted job", async scope => {
    let post = 0;
    fetchMock.mockImplementation(async (path: string, options: RequestInit) => {
      if (options.method === "POST") { post++; return json({ job_slug: newsCollectJob.slug, status: "queued" }, 202); }
      return json(path.includes("job_slug=") ? running() : newsCollectionStatus);
    });
    render(<NewsCollectionWorkspace initialSources={[{ ...newsSource, active: true }]} initialStatus={newsCollectionStatus} />);
    const button = screen.getByRole("button", { name: scope === "all" ? "Проверить все включённые" : `Проверить: ${newsSource.name}` });
    fireEvent.click(button); fireEvent.click(button);
    await screen.findByText("Проверяем источники");
    expect(post).toBe(1);
    const call = fetchMock.mock.calls.find(([, options]) => options.method === "POST")!;
    expect(call[0]).toBe("/api/admin/news/jobs/collect");
    expect(JSON.parse(call[1].body)).toEqual(scope === "all" ? {} : { source_slug: newsSource.slug });
    expect(fetchMock.mock.calls.some(([path]) => path.includes(`?job_slug=${newsCollectJob.slug}`))).toBe(true);
  });

  it("allows checking an individual paused source while all-disabled action is unavailable", async () => {
    render(<NewsCollectionWorkspace initialSources={[newsSource]} initialStatus={newsCollectionStatus} />);
    expect((screen.getByRole("button", { name: "Проверить все включённые" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: `Проверить: ${newsSource.name}` }) as HTMLButtonElement).disabled).toBe(false);
    await act(async () => {});
  });

  it("returns to automatic tracking after an initiated job completes", async () => {
    let posted = false;
    fetchMock.mockImplementation(async (path: string, options: RequestInit) => {
      if (options.method === "POST") { posted = true; return json({ job_slug: newsCollectJob.slug }, 202); }
      return json(path.includes("job_slug=") || posted ? analyzed() : newsCollectionStatus);
    });
    render(<NewsCollectionWorkspace initialSources={[{ ...newsSource, active: true }]} initialStatus={newsCollectionStatus} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить все включённые" }));
    await screen.findByText("Проверка завершена");
    expect(router.refresh).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/admin/news/collection-status").length).toBeGreaterThan(1);
  });

  it("pauses hidden tabs, resumes on focus and aborts on unmount", async () => {
    vi.useFakeTimers(); const value = running();
    const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    fetchMock.mockImplementation(async () => json(value));
    const view = render(<NewsCollectionWorkspace initialSources={[newsSource]} initialStatus={value} />);
    await act(async () => {});
    hidden.mockReturnValue(true); fireEvent(document, new Event("visibilitychange"));
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(fetchMock).toHaveBeenCalledOnce();
    hidden.mockReturnValue(false); fireEvent(window, new Event("focus"));
    await act(async () => {});
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const signal = fetchMock.mock.calls[1][1].signal;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(20000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("keeps the last state through connection errors, retries and preserves focus", async () => {
    fetchMock.mockResolvedValue(json({ detail: "private" }, 500));
    render(<NewsCollectionWorkspace initialSources={[newsSource]} initialStatus={running()} />);
    const toggle = screen.getByRole("switch"); toggle.focus();
    await screen.findByText(/Показано последнее полученное состояние/);
    expect(document.activeElement).toBe(toggle);
    expect(screen.getByText("Проверяем источники")).toBeTruthy();
    expect(screen.queryByText("private")).toBeNull();
    fetchMock.mockResolvedValue(json(analyzed()));
    fireEvent.click(screen.getByRole("button", { name: "Обновить состояние" }));
    await screen.findByText("Проверка завершена");
    expect(screen.queryByText(/Показано последнее/)).toBeNull();
  });

  it("redirects an expired session and stops polling", async () => {
    vi.useFakeTimers(); fetchMock.mockResolvedValue(json({}, 401));
    render(<NewsCollectionWorkspace initialSources={[newsSource]} initialStatus={running()} />);
    await act(async () => {});
    expect(router.replace).toHaveBeenCalledWith("/admin/login");
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("supports the same live state on the runs page and a selected paused source", async () => {
    fetchMock.mockImplementation(async (_path: string, options: RequestInit) => options.method === "POST" ? json({ job_slug: newsCollectJob.slug }, 202) : json(running()));
    render(<NewsCollectionWorkspace mode="runs" initialSources={[newsSource]} initialStatus={newsCollectionStatus} />);
    fireEvent.change(screen.getByLabelText("Источник для сбора"), { target: { value: newsSource.slug } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить сейчас" }));
    await screen.findByText("Проверяем источники");
    const call = fetchMock.mock.calls.find(([, options]) => options.method === "POST")!;
    expect(JSON.parse(call[1].body)).toEqual({ source_slug: newsSource.slug });
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("honest terminal progress", () => {
  it.each(["missing_llm", "paused", "insufficient_text", "unavailable"] as const)("explains blocked %s work without claiming a running model", reason => {
    const value = analyzed(); value.analysis.completed = 2; value.analysis.blocked = 1; value.analysis.blocked_reasons[reason] = 1;
    render(<NewsCollectionProgress status={value} error="" onRetry={() => {}} />);
    expect(screen.getByText("Сбор завершён, часть материалов ожидает анализа")).toBeTruthy();
    expect(screen.queryByText("Сбор завершён, идёт анализ")).toBeNull();
    expect(screen.getByRole("progressbar", { name: "Готовые анализы" }).getAttribute("value")).toBe("2");
  });

  it("does not fabricate model work for unchanged materials and escapes failure text", () => {
    const value = analyzed(); value.analysis = structuredClone(newsCollectionStatus.analysis); value.collection.new = 0; value.collection.unchanged = 50; value.collection.sources_failed = 1;
    value.job!.error = '<img src=x onerror="alert(1)">';
    const { container } = render(<NewsCollectionProgress status={value} error="" onRetry={() => {}} />);
    expect(screen.getByText("Проверка завершена с ошибками")).toBeTruthy();
    expect(screen.queryByRole("progressbar", { name: "Готовые анализы" })).toBeNull();
    expect(screen.getByText("Новых и изменённых материалов для анализа нет.")).toBeTruthy();
    expect(screen.getByText(value.job!.error!)).toBeTruthy();
    expect(container.querySelector("img")).toBeNull();
  });
});
