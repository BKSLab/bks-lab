import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("@/lib/api", () => ({
  getProjects: vi.fn(async () => [
    {
      slug: "demo",
      title: "Проект из API",
      excerpt: "Описание проекта",
      cover_image: "/images/projects/service-desk.webp",
      tags: ["Python"],
      status: "active",
      featured: true,
      order: 1,
    },
  ]),
  getLatestArticles: vi.fn(async () => []),
  getNotesFeed: vi.fn(async () => ({ items: [], next_cursor: null, newest_cursor: null, has_more: false })),
}));

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

import HomePage from "@/app/(public)/page";
import { getNotesFeed } from "@/lib/api";

describe("home page", () => {
  it("renders the API project, all sections and a single H1", async () => {
    render(await HomePage());

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Проверяю идеи на практике.",
      }),
    ).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Эксперименты с AI, собственные инструменты и новости технологий — с авторским разбором и выводами.")).toBeTruthy();
    expect(screen.queryByText("РАЗРАБОТКА · ПРОЕКТЫ · ИДЕИ")).toBeNull();
    expect(
      screen.getByRole("link", { name: "Проект из API" }).getAttribute("href"),
    ).toBe("/projects/demo");
    for (const name of [
      "Направления",
      "Мои проекты",
      "Последние статьи",
      "Заметки на полях",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeTruthy();
    }
    const notes = screen.getByRole("complementary", { name: "Заметки на полях" });
    expect(within(notes).getByText("Заметки скоро появятся.")).toBeTruthy();
    expect(within(notes).getByRole("link", { name: "Все заметки" }).getAttribute("href"))
      .toBe("/notes");
  });

  it("renders complete notes in the accessible sidebar with local anchors", async () => {
    vi.mocked(getNotesFeed).mockResolvedValueOnce({ items: [
      {
        slug: "small-steps",
        title: "Маленькие шаги",
        excerpt: "Рабочая идея начинается с небольшого изменения.",
        published_at: "2026-10-13",
        reading_time: 1,
        tags: [],
        related_article: null,
        content_html: "<p>Полный текст заметки.</p>",
      },
    ], next_cursor: null, newest_cursor: "head", has_more: false });
    const { container } = render(await HomePage());
    const notes = screen.getByRole("complementary", { name: "Заметки на полях" });
    expect(within(notes).getByRole("link", { name: "Маленькие шаги" }).getAttribute("href"))
      .toBe("#note-small-steps");
    expect(within(notes).getByText("Полный текст заметки.")).toBeTruthy();
    expect(within(notes).getByText("bks-lab.ru")).toBeTruthy();
    expect(within(notes).getByRole("region", { name: "Лента заметок" }).getAttribute("tabindex")).toBe("0");
    expect(within(notes).queryByText("Заметки скоро появятся.")).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });
});
