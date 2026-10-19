import { existsSync, mkdirSync, mkdtempSync, rmdirSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("next/navigation", () => ({
  usePathname: () => "/about",
  useSearchParams: () => new URLSearchParams(),
}));

import AboutPage from "@/app/(public)/about/page";
import PublicLayout from "@/app/(public)/layout";

let fixtureDirectory: string;

beforeEach(() => {
  fixtureDirectory = mkdtempSync(join(tmpdir(), "bks-lab-about-test-"));
  mkdirSync(join(fixtureDirectory, "public", "images"), { recursive: true });
  vi.spyOn(process, "cwd").mockReturnValue(fixtureDirectory);
  Object.defineProperty(navigator, "sendBeacon", {
    value: vi.fn(),
    configurable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  const portrait = join(fixtureDirectory, "public", "images", "author.jpg");
  if (existsSync(portrait)) unlinkSync(portrait);
  rmdirSync(join(fixtureDirectory, "public", "images"));
  rmdirSync(join(fixtureDirectory, "public"));
  rmdirSync(fixtureDirectory);
});

describe("about page", () => {
  it("keeps the illustrated story accessible when the opening portrait is absent", async () => {
    const { container } = render(
      <PublicLayout>
        <AboutPage />
      </PublicLayout>,
    );

    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Обо мне" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Работа для всех" })).toBeTruthy();
    expect(screen.queryByRole("img", { name: "Кирилл Барабанщиков идёт по городской улице" })).toBeNull();
    expect(screen.getByRole("link", { name: "Мои проекты" }).getAttribute("href"))
      .toBe("/projects");
    expect(screen.getByRole("link", { name: "Читать блог" }).getAttribute("href"))
      .toBe("/blog");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("reserves photo dimensions and defers the four photos below the opening", () => {
    writeFileSync(join(fixtureDirectory, "public", "images", "author.jpg"), "");
    render(<AboutPage />);

    const portrait = screen.getByRole("img", { name: "Кирилл Барабанщиков идёт по городской улице" });
    expect(portrait.getAttribute("width")).toBe("3072");
    expect(portrait.getAttribute("height")).toBe("4080");
    expect(portrait.getAttribute("src")).toContain("author.jpg");
    expect(portrait.getAttribute("loading")).toBe("eager");

    const photos = screen.getAllByRole("img");
    expect(photos).toHaveLength(5);
    for (const photo of photos.filter((image) => image !== portrait)) {
      expect(Number(photo.getAttribute("width"))).toBeGreaterThan(0);
      expect(Number(photo.getAttribute("height"))).toBeGreaterThan(0);
      expect(photo.getAttribute("loading")).toBe("lazy");
      expect(photo.closest("figure")?.querySelector("figcaption")?.textContent).toBeTruthy();
    }
  });
});
