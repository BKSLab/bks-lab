import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NewsSourceCatalogue } from "@/components/admin/news/NewsSourceCatalogue";
import { newsSource } from "./news-fixtures";

describe("complete source catalogue", () => {
  it("displays every research row and preserves alternate feed addresses", () => {
    render(<NewsSourceCatalogue sources={[]} />);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(98);
    expect(screen.getByRole("status").textContent).toContain("98 из 98");
    expect(screen.getByRole("heading", { name: /^HN RSS/ })).toBeTruthy();
    const simon = screen.getAllByRole("heading", { name: /^Simon Willison/ })[0].closest("li")!;
    fireEvent.click(within(simon).getByText("Адреса источника (3)"));
    expect(within(simon).getByRole("link", { name: "https://simonwillison.net/atom/everything/ (в новой вкладке)" }).getAttribute("href")).toBe("https://simonwillison.net/atom/everything/");
  });

  it("combines search, group, usage and priority filters and resets them", () => {
    render(<NewsSourceCatalogue sources={[]} />);
    fireEvent.change(screen.getByLabelText("Раздел каталога"), { target: { value: "russian" } });
    expect(screen.getByRole("status").textContent).toContain("15 из 98");
    fireEvent.change(screen.getByLabelText("Приоритет каталога"), { target: { value: "B" } });
    fireEvent.change(screen.getByLabelText("Способ использования"), { target: { value: "auto" } });
    fireEvent.change(screen.getByLabelText("Поиск по названию, адресу и описанию"), { target: { value: "Т-БАНК корпоративный" } });
    expect(screen.getByRole("status").textContent).toContain("1 из 98");
    expect(screen.getByRole("link", { name: "Проверить и подключить: Т-Банк AI Research" }).getAttribute("href")).toBe("/admin/news/sources/new?catalogue=ru-tbank");
    fireEvent.change(screen.getByLabelText("Раздел каталога"), { target: { value: "labs" } });
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
    expect(screen.getByText(/По этим условиям источников нет/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(98);
  });

  it("searches alternate URLs and preserves tools without offering unsupported collection", () => {
    render(<NewsSourceCatalogue sources={[]} />);
    fireEvent.change(screen.getByLabelText("Поиск по названию, адресу и описанию"), { target: { value: "search_by_date" } });
    expect(screen.getByRole("heading", { name: /^Hacker News Algolia Search/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Проверить и подключить/ })).toBeNull();
    fireEvent.change(screen.getByLabelText("Поиск по названию, адресу и описанию"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Способ использования"), { target: { value: "read" } });
    expect(screen.getByRole("status").textContent).toContain("5 из 98");
    expect(screen.queryByRole("link", { name: /Проверить и подключить/ })).toBeNull();
  });

  it.each([true, false])("recognizes an existing source and its active=%s state across duplicate authors", active => {
    render(<NewsSourceCatalogue sources={[{ ...newsSource, url: "https://simonwillison.net/atom/entries", active }]} />);
    fireEvent.change(screen.getByLabelText("Поиск по названию, адресу и описанию"), { target: { value: "Simon Willison" } });
    expect(screen.getAllByRole("link", { name: "Настроить источник: Simon Willison" })).toHaveLength(2);
    expect(screen.getAllByText(active ? "Подключён" : "На паузе")).toHaveLength(2);
    expect(screen.queryByRole("link", { name: "Проверить и подключить: Simon Willison" })).toBeNull();
  });
});
