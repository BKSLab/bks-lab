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
  getLatestNotes: vi.fn(async () => []),
}));

import HomePage from "@/app/(public)/page";
import { getLatestNotes } from "@/lib/api";

describe("home page", () => {
  it("renders the API project, all sections and a single H1", async () => {
    render(await HomePage());

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Разработка. Управление. Искусственный интеллект. Идеи, которые работают.",
      }),
    ).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
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

  it("renders published notes as an accessible sidebar with links to the full notes", async () => {
    vi.mocked(getLatestNotes).mockResolvedValueOnce([
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
    ]);
    const { container } = render(await HomePage());
    const notes = screen.getByRole("complementary", { name: "Заметки на полях" });
    expect(within(notes).getByRole("link", { name: "Маленькие шаги" }).getAttribute("href"))
      .toBe("/notes#note-small-steps");
    expect(within(notes).getByText("Рабочая идея начинается с небольшого изменения.")).toBeTruthy();
    expect(within(notes).queryByText("Заметки скоро появятся.")).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });
});
