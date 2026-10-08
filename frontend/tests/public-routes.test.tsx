import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import PublicLayout from "@/app/(public)/layout";
import PublicNotFound from "@/app/(public)/not-found";
import PrivacyPage from "@/app/(public)/privacy/page";
import ErrorPage from "@/app/error";
import RootNotFound from "@/app/not-found";

beforeEach(() => {
  Object.defineProperty(navigator, "sendBeacon", {
    value: vi.fn(),
    configurable: true,
    writable: true,
  });
});

function expectPublicLandmarks(heading: string) {
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getAllByRole("banner")).toHaveLength(1);
  expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(screen.getByRole("heading", { level: 1, name: heading })).toBeTruthy();
  expect(
    screen.getAllByRole("link", { name: "Перейти к основному содержимому" }),
  ).toHaveLength(1);
  expect(screen.getByRole("main").id).toBe("main-content");
}

describe("public route fallbacks", () => {
  it("provides the privacy destination inside the shared layout", () => {
    render(
      <PublicLayout>
        <PrivacyPage />
      </PublicLayout>,
    );

    expectPublicLandmarks("Политика конфиденциальности");
    expect(
      screen
        .getByRole("link", { name: "Политика конфиденциальности" })
        .getAttribute("href"),
    ).toBe("/privacy");
    expect(screen.getByRole("heading", { level: 2, name: "Вопросы о данных" })).toBeTruthy();
    expect(screen.getByText(/Рекламные блоки отключены/)).toBeTruthy();
  });

  it.each([
    ["unknown URL", <RootNotFound key="root" />],
    [
      "notFound() inside the public group",
      <PublicLayout key="public">
        <PublicNotFound />
      </PublicLayout>,
    ],
  ])("keeps one public shell for %s", async (_name, page) => {
    const { container } = render(page);

    expectPublicLandmarks("Страница не найдена");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("keeps public navigation and the retry action in the root error fallback", () => {
    const reset = vi.fn();
    render(<ErrorPage error={new Error("render failed")} reset={reset} />);

    expectPublicLandmarks("Что-то пошло не так");
    fireEvent.click(screen.getByRole("button", { name: "Попробовать снова" }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
