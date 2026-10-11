import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { fetchMock } = vi.hoisted(() => ({ fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }) }));

import { ImageInsertDialog } from "@/components/admin/editor/ImageInsertDialog";
import { ContentHtml } from "@/components/content/ContentHtml";

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

const imageFixture = {
  id: 1,
  path: "/uploads/shared/one.webp",
  original_name: "one.png",
  mime: "image/webp",
  size_bytes: 1200,
  width: 640,
  height: 480,
  created_at: "2026-10-20T10:00:00Z",
};

describe("ImageInsertDialog", () => {
  it("loads and lists existing images for selection", async () => {
    fetchMock.mockResolvedValue(json([imageFixture]));
    render(<ImageInsertDialog open onClose={vi.fn()} onInsert={vi.fn()} />);
    const thumb = await screen.findByRole("button", { name: "Выбрать: one.png" });
    expect(thumb.getAttribute("aria-pressed")).toBe("false");
    expect(thumb.querySelector("img")!.getAttribute("src")).toBe("/uploads/shared/one.webp");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/content/images");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
  });

  it("inserts an existing image after asking for alt text", async () => {
    fetchMock.mockResolvedValue(json([imageFixture]));
    const onInsert = vi.fn();
    const onClose = vi.fn();
    render(<ImageInsertDialog open onClose={onClose} onInsert={onInsert} />);
    fireEvent.click(await screen.findByRole("button", { name: "Выбрать: one.png" }));
    fireEvent.change(screen.getByLabelText(/Альтернативный текст для «one\.png»/), { target: { value: "Схема архитектуры" } });
    fireEvent.click(screen.getByRole("button", { name: "Вставить" }));
    expect(onInsert).toHaveBeenCalledWith("![Схема архитектуры](/uploads/shared/one.webp)");
    expect(onClose).toHaveBeenCalled();
  });

  it("uploads a file and inserts the uploaded path as markdown", async () => {
    fetchMock
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(json({ ...imageFixture, id: 2, path: "/uploads/shared/two.webp", original_name: "two.png" }, 201));
    const onInsert = vi.fn();
    const onClose = vi.fn();
    render(<ImageInsertDialog open onClose={onClose} onInsert={onInsert} />);
    await screen.findByText("Загруженных изображений пока нет.");
    const file = new File(["bytes"], "two.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Файл изображения (JPEG, PNG или WebP)"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("Альтернативный текст (alt)"), { target: { value: "Скриншот" } });
    fireEvent.click(screen.getByRole("button", { name: "Загрузить" }));
    await waitFor(() => expect(onInsert).toHaveBeenCalledWith("![Скриншот](/uploads/shared/two.webp)"));
    expect(onClose).toHaveBeenCalled();
    const [url, options] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/admin/content/images");
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("same-origin");
    expect(options.headers).toEqual({ Accept: "application/json" });
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBe(file);
  });

  it("shows the error in the alert area and keeps the dialog open when the upload fails", async () => {
    fetchMock
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(new Response("Unauthorized", { status: 401 }));
    const onClose = vi.fn();
    render(<ImageInsertDialog open onClose={onClose} onInsert={vi.fn()} />);
    await screen.findByText("Загруженных изображений пока нет.");
    fireEvent.change(screen.getByLabelText("Файл изображения (JPEG, PNG или WebP)"), {
      target: { files: [new File(["x"], "pic.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Загрузить" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Сессия завершилась"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    fetchMock.mockResolvedValue(json([]));
    const onClose = vi.fn();
    render(<ImageInsertDialog open onClose={onClose} onInsert={vi.fn()} />);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("has no detectable accessibility violations when open", async () => {
    fetchMock.mockResolvedValue(json([imageFixture]));
    const { container } = render(<ImageInsertDialog open onClose={vi.fn()} onInsert={vi.fn()} />);
    await screen.findByRole("button", { name: "Выбрать: one.png" });
    expect((await axe(container)).violations).toEqual([]);
  });
});

describe("ContentHtml ad placeholder", () => {
  const html = '<p>первая часть</p><div data-ad-slot="article-inline"></div><p>вторая часть</p><div data-ad-slot="article-inline"></div><p>третья часть</p>';

  it("splits the html on the placeholder and renders parts around the custom slot renderer", () => {
    const renderAdSlot = vi.fn((index: number) => <div data-testid={`ad-${index}`}>Рекламный блок {index + 1}</div>);
    const { container } = render(<ContentHtml html={html} renderAdSlot={renderAdSlot} />);
    expect(container.querySelectorAll(".prose-content")).toHaveLength(3);
    expect(container.querySelectorAll('[data-testid^="ad-"]')).toHaveLength(2);
    expect(renderAdSlot).toHaveBeenCalledWith(0);
    expect(renderAdSlot).toHaveBeenCalledWith(1);
    const parts = Array.from(container.querySelectorAll(".prose-content")).map((part) => part.textContent);
    expect(parts).toEqual(["первая часть", "вторая часть", "третья часть"]);
  });

  it("keeps a single prose-content div when there is no placeholder", () => {
    const { container } = render(<ContentHtml html="<p>только текст</p>" />);
    expect(container.querySelectorAll(".prose-content")).toHaveLength(1);
    expect(container.firstElementChild!.className).toBe("prose-content");
    expect(container.textContent).toBe("только текст");
  });
});
