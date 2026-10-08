import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({ router: { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }, fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

import { NewsSourceForm } from "@/components/admin/news/NewsSourceForm";
import { NewsDecisionForm } from "@/components/admin/news/NewsDecisionForm";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { NewsJobProgress } from "@/components/admin/news/NewsJobProgress";
import { NewsSettingsForm } from "@/components/admin/news/NewsSettingsForm";
import { NewsTaxonomyManager } from "@/components/admin/news/NewsTaxonomyManager";
import { newsCategory, newsJob, newsSettings, newsSource, newsTopic } from "./news-fixtures";

beforeEach(() => { fetchMock.mockReset(); Object.values(router).forEach(fn => fn.mockReset()); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

function fillSource() {
  fireEvent.change(screen.getByLabelText("Название (обязательно)"), { target: { value: "Технический блог" } });
  fireEvent.change(screen.getByLabelText("URL источника (обязательно)"), { target: { value: "https://example.org/" } });
}

describe("source discovery and saving", () => {
  it("has labeled inputs and blocks saving an untested source with a focused explanation", async () => {
    const { container } = render(<NewsSourceForm topics={[newsTopic]} categories={[newsCategory]} />);
    fillSource();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить источник" }));
    const error = await screen.findByRole("alert");
    expect(error.textContent).toContain("Сначала проверьте");
    expect(document.activeElement).toBe(error);
    expect(fetchMock).not.toHaveBeenCalled();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("queues discovery, previews the resolved feed, and saves its job proof with editor settings", async () => {
    fetchMock.mockResolvedValueOnce(json({ job_id: 9, status: "queued" }, 202)).mockResolvedValueOnce(json(newsJob)).mockResolvedValueOnce(json(newsSource));
    render(<NewsSourceForm topics={[newsTopic]} categories={[newsCategory]} />);
    fillSource();
    fireEvent.click(screen.getByLabelText("AI Engineering"));
    fireEvent.click(screen.getByRole("button", { name: "Проверить источник" }));
    await screen.findByRole("link", { name: "Новая публикация (в новой вкладке)" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/news/sources/discover");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ url: "https://example.org/", config: {} });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/news/jobs/9");
    expect((screen.getByLabelText("URL источника (обязательно)") as HTMLInputElement).value).toBe("https://example.org/feed.xml");
    fireEvent.click(screen.getByRole("button", { name: "Сохранить источник" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/admin/news/sources"));
    const [url, options] = fetchMock.mock.calls[2];
    expect(url).toBe("/api/admin/news/sources");
    expect(options.credentials).toBe("same-origin");
    expect(options.cache).toBe("no-store");
    expect(JSON.parse(options.body)).toMatchObject({ discovery_job_id: 9, url: "https://example.org/feed.xml", kind: "rss", active: false, topic_ids: [1], trust_score: 50, interval_hours: 6 });
  });

  it("invalidates proof after editing the discovered URL", async () => {
    fetchMock.mockResolvedValueOnce(json({ job_id: 9, status: "queued" }, 202)).mockResolvedValueOnce(json(newsJob));
    render(<NewsSourceForm topics={[]} categories={[]} />);
    fillSource();
    fireEvent.click(screen.getByRole("button", { name: "Проверить источник" }));
    await screen.findByRole("link", { name: "Новая публикация (в новой вкладке)" });
    fireEvent.change(screen.getByLabelText("URL источника (обязательно)"), { target: { value: "https://example.net/feed" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить источник" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Сначала проверьте");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("allows editing metadata of an already verified source without another discovery", async () => {
    fetchMock.mockResolvedValue(json(newsSource));
    render(<NewsSourceForm source={newsSource} topics={[newsTopic]} categories={[newsCategory]} />);
    fireEvent.change(screen.getByLabelText("Название (обязательно)"), { target: { value: "Новое название" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить источник" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/admin/news/sources"));
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).not.toHaveProperty("discovery_job_id");
  });

  it("requires rechecking HTML after selectors change", async () => {
    const htmlJob = { ...newsJob, result: { ...newsJob.result, kind: "html", url: "https://example.org/" } };
    fetchMock.mockResolvedValueOnce(json({ job_id: 9, status: "queued" }, 202)).mockResolvedValueOnce(json(htmlJob));
    render(<NewsSourceForm topics={[]} categories={[]} />);
    fillSource();
    fireEvent.change(screen.getByLabelText("Способ получения"), { target: { value: "html" } });
    fireEvent.change(screen.getByLabelText("Блок публикации"), { target: { value: " article " } });
    fireEvent.change(screen.getByLabelText("Заголовок"), { target: { value: "h2" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить источник" }));
    await screen.findByRole("link", { name: "Новая публикация (в новой вкладке)" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ url: "https://example.org/", kind: "html", config: { item_selector: "article", title_selector: "h2" } });
    fireEvent.change(screen.getByLabelText("Блок публикации"), { target: { value: ".post" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить источник" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Сначала проверьте");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("only prefills a catalogue suggestion, never auto-enables or saves it", () => {
    render(<NewsSourceForm topics={[]} categories={[]} />);
    fireEvent.change(screen.getByLabelText("Подставить адрес из каталога"), { target: { value: "0" } });
    expect((screen.getByLabelText("Название (обязательно)") as HTMLInputElement).value).toBe("Simon Willison — статьи");
    expect((screen.getByLabelText("Включить регулярный сбор") as HTMLInputElement).checked).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("editorial actions and jobs", () => {
  it("saves decision, format and comment using the session identity", async () => {
    fetchMock.mockResolvedValue(json({ id: 1 }));
    render(<NewsDecisionForm itemId={4} />);
    fireEvent.change(screen.getByLabelText("Назначение"), { target: { value: "short_news_candidate" } });
    fireEvent.change(screen.getByLabelText("Комментарий редактора"), { target: { value: " Проверить цифры " } });
    fireEvent.click(screen.getByRole("button", { name: "В работу" }));
    await waitFor(() => expect(router.refresh).toHaveBeenCalledOnce());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ decision: "in_work", format: "short_news_candidate", comment: "Проверить цифры" });
    expect(screen.getByRole("status").textContent).toContain("Решение сохранено");
  });

  it.each([401, 422, 500])("handles status %s safely and restores the form", async status => {
    fetchMock.mockResolvedValue(json({ detail: "private-upstream-error" }, status));
    render(<NewsDecisionForm itemId={4} />);
    fireEvent.click(screen.getByRole("button", { name: "Отложить" }));
    const error = await screen.findByRole("alert");
    expect(error.textContent).not.toContain("private-upstream-error");
    expect(document.activeElement).toBe(error);
    expect((screen.getByRole("button", { name: "Отложить" }) as HTMLButtonElement).disabled).toBe(false);
    if (status === 401) expect(router.replace).toHaveBeenCalledWith("/admin/login");
  });

  it("prevents duplicate submissions while a decision is pending", async () => {
    let resolve: (value: Response) => void = () => {};
    fetchMock.mockReturnValue(new Promise<Response>(done => { resolve = done; }));
    render(<NewsDecisionForm itemId={4} />);
    fireEvent.click(screen.getByRole("button", { name: "В работу" }));
    fireEvent.click(screen.getByRole("button", { name: "Отклонить" }));
    expect(fetchMock).toHaveBeenCalledOnce();
    expect((screen.getByRole("button", { name: "Отклонить" }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => resolve(json({ id: 1 })));
  });

  it("polls a queued job, announces completion, and stops polling", async () => {
    vi.useFakeTimers();
    const finish = vi.fn();
    fetchMock.mockResolvedValueOnce(json({ ...newsJob, status: "running", progress: { sources_total: 2, sources_done: 1 } })).mockResolvedValueOnce(json(newsJob));
    const { unmount } = render(<NewsJobProgress jobId={9} onFinish={finish} />);
    await act(async () => {});
    expect(screen.getAllByRole("status").some(status => status.textContent?.includes("Выполняется"))).toBe(true);
    expect(screen.getByText("Проверено источников")).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(screen.getAllByRole("status").some(status => status.textContent?.includes("Завершено"))).toBe(true);
    expect(finish).toHaveBeenCalledOnce();
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    unmount();
  });

  it("retries a failed status request without starting another job", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(json(newsJob));
    render(<NewsJobProgress jobId={9} />);
    expect((await screen.findByRole("alert")).textContent).toContain("Нет связи");
    fireEvent.click(screen.getByRole("button", { name: "Обновить статус" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(fetchMock.mock.calls.every(([url]) => url === "/api/admin/news/jobs/9")).toBe(true);
  });

  it("queues a manual run for the selected source", async () => {
    fetchMock.mockResolvedValueOnce(json({ job_id: 9, status: "queued" }, 202)).mockResolvedValueOnce(json({ ...newsJob, kind: "collect", result: {} }));
    render(<NewsJobLauncher sources={[newsSource]} />);
    fireEvent.change(screen.getByLabelText("Источник для сбора"), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить сейчас" }));
    await screen.findByRole("link", { name: "Открыть задание № 9" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/news/jobs/collect");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source_id: 7 });
  });
});

describe("editorial settings and taxonomy", () => {
  it("rejects incorrect score weights and focuses the explanation", async () => {
    render(<NewsSettingsForm settings={newsSettings} />);
    const fields = screen.getAllByLabelText("Соответствие тематике, %");
    fireEvent.change(fields[0], { target: { value: "41" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить настройки" }));
    const error = await screen.findByRole("alert");
    expect(error.textContent).toContain("Сумма весов");
    expect(document.activeElement).toBe(error);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("saves policy and schedule without provider secrets or financial settings", async () => {
    fetchMock.mockResolvedValue(json(newsSettings));
    const { container } = render(<NewsSettingsForm settings={newsSettings} />);
    fireEvent.click(screen.getByRole("button", { name: "Сохранить настройки" }));
    await waitFor(() => expect(router.refresh).toHaveBeenCalledOnce());
    const editable = Object.fromEntries(Object.entries(newsSettings).filter(([key]) => !key.startsWith("llm_")));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(editable);
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("adds a topic and resets the creation form", async () => {
    fetchMock.mockResolvedValue(json(newsTopic));
    render(<NewsTaxonomyManager topics={[]} categories={[]} />);
    const region = screen.getByRole("heading", { name: "Темы" }).closest("section")!;
    fireEvent.change(within(region).getByLabelText("Название (обязательно)"), { target: { value: " AI Engineering " } });
    fireEvent.click(within(region).getByRole("button", { name: "Добавить тему" }));
    await waitFor(() => expect(router.refresh).toHaveBeenCalledOnce());
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/news/topics");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ name: "AI Engineering", description: "", active: true });
    expect((within(region).getByLabelText("Название (обязательно)") as HTMLInputElement).value).toBe("");
  });
});
