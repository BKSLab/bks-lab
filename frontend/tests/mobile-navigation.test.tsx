import { act, fireEvent, render, screen } from "@testing-library/react";
import Link from "next/link";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/blog",
}));

import { MobileNavigation } from "@/components/navigation/MobileNavigation";

describe("MobileNavigation", () => {
  it("toggles aria-expanded and the panel via the button", () => {
    render(<MobileNavigation />);

    const button = screen.getByRole("button", { name: "Открыть меню" });
    expect(button.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(button);

    const expanded = screen.getByRole("button", { name: "Закрыть меню" });
    expect(expanded.getAttribute("aria-expanded")).toBe("true");
    const panel = screen.getByRole("navigation", {
      name: "Мобильная навигация",
    });
    expect(panel.id).toBe(expanded.getAttribute("aria-controls"));
    // Active section is marked for assistive technology.
    expect(
      screen.getByRole("link", { name: "Блог" }).getAttribute("aria-current"),
    ).toBe("page");
  });

  it("closes on Escape and returns focus to the button", () => {
    render(<MobileNavigation />);

    const button = screen.getByRole("button", { name: "Открыть меню" });
    fireEvent.click(button);
    expect(
      screen.queryByRole("navigation", { name: "Мобильная навигация" }),
    ).not.toBeNull();

    act(() => screen.getByRole("link", { name: "Блог" }).focus());

    fireEvent.keyDown(document, { key: "Escape" });

    expect(
      screen.queryByRole("navigation", { name: "Мобильная навигация" }),
    ).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it("stays open while focus moves between the toggle and panel links", () => {
    render(<MobileNavigation />);
    const button = screen.getByRole("button", { name: "Открыть меню" });
    act(() => button.focus());
    fireEvent.click(button);

    act(() => screen.getByRole("link", { name: "Блог" }).focus());
    act(() => screen.getByRole("link", { name: "Связаться" }).focus());
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(
      screen.getByRole("navigation", { name: "Мобильная навигация" }),
    ).toBeTruthy();
  });

  it("closes on focus leaving for a footer link without moving that focus", () => {
    render(
      <>
        <MobileNavigation />
        <footer><Link href="/">Главная в футере</Link></footer>
      </>,
    );
    const button = screen.getByRole("button", { name: "Открыть меню" });
    fireEvent.click(button);
    act(() => screen.getByRole("link", { name: "Связаться" }).focus());

    const footerLink = screen.getByRole("link", { name: "Главная в футере" });
    act(() => footerLink.focus());

    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(
      screen.queryByRole("navigation", { name: "Мобильная навигация" }),
    ).toBeNull();
    expect(document.activeElement).toBe(footerLink);
  });

  it("closes without taking focus back when navigation focuses the page H1", () => {
    render(
      <>
        <MobileNavigation />
        <main><h1 tabIndex={-1}>Новая страница</h1></main>
      </>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Открыть меню" }));
    act(() => screen.getByRole("link", { name: "Проекты" }).focus());

    const heading = screen.getByRole("heading", { level: 1 });
    act(() => heading.focus());

    expect(
      screen.queryByRole("navigation", { name: "Мобильная навигация" }),
    ).toBeNull();
    expect(document.activeElement).toBe(heading);
  });
});
