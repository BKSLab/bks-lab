import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

describe("home page", () => {
  it("renders the API project, all sections and a single H1", async () => {
    render(await HomePage());

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Технологии для более открытого мира",
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
  });
});
