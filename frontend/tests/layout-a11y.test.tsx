import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import PublicLayout from "@/app/(public)/layout";
import { AppHeader } from "@/components/layout/AppHeader";

beforeEach(() => {
  Object.defineProperty(navigator, "sendBeacon", {
    value: vi.fn(),
    configurable: true,
    writable: true,
  });
});

describe("public layout", () => {
  it("renders skip link, banner, main and contentinfo landmarks", () => {
    render(
      <PublicLayout>
        <h1>Заголовок страницы</h1>
      </PublicLayout>,
    );

    const skipLink = screen.getByRole("link", {
      name: "Перейти к основному содержимому",
    });
    expect(skipLink.getAttribute("href")).toBe("#main-content");

    expect(screen.getByRole("banner")).toBeTruthy();
    const main = screen.getByRole("main");
    expect(main.id).toBe("main-content");
    expect(main.getAttribute("tabindex")).toBe("-1");
    expect(screen.getByRole("contentinfo")).toBeTruthy();
  });

  it("has no critical axe violations", async () => {
    const { container } = render(
      <PublicLayout>
        <h1>Заголовок страницы</h1>
      </PublicLayout>,
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe("AppHeader", () => {
  it("marks the current section with aria-current", () => {
    render(<AppHeader />);

    const current = screen.getByRole("link", { name: "Главная" });
    expect(current.getAttribute("aria-current")).toBe("page");
  });

  it("exposes accessible names for icon-only controls", () => {
    render(<AppHeader />);

    expect(
      screen.getByRole("link", { name: "BKS Lab — на главную" }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Поиск по блогу" })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Переключить на тёмную тему" }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Открыть меню" })).toBeTruthy();
  });

  it("has no critical axe violations", async () => {
    const { container } = render(<AppHeader />);

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
