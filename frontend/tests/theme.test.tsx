import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/navigation/ThemeToggle";
import { themeInitScript, type Theme } from "@/lib/theme";

class MockMediaQueryList extends EventTarget {
  readonly media = "(prefers-color-scheme: dark)";
  matches = false;

  change(matches: boolean) {
    if (this.matches === matches) return;
    this.matches = matches;
    this.dispatchEvent(Object.assign(new Event("change"), {
      matches,
      media: this.media,
    }));
  }
}

let media: MockMediaQueryList;
let themeColor: HTMLMetaElement;

function bootstrap() {
  // Execute the actual pre-paint script rather than a duplicate implementation.
  new Function(themeInitScript)();
}

function expectTheme(theme: Theme, preference: Theme | "system") {
  expect(document.documentElement.dataset.theme).toBe(theme);
  expect(document.documentElement.dataset.themePreference).toBe(preference);
  expect(themeColor.content).toBe(theme === "dark" ? "#071827" : "#f4f7f9");
}

function toggleButton(theme: Theme) {
  return screen.getByRole("button", {
    name: theme === "dark"
      ? "Переключить на светлую тему"
      : "Переключить на тёмную тему",
  });
}

function changeStoredTheme(key: string | null, newValue: string | null) {
  const oldValue = key === null ? null : localStorage.getItem(key);
  if (key === null) localStorage.clear();
  else if (newValue === null) localStorage.removeItem(key);
  else localStorage.setItem(key, newValue);

  act(() => {
    window.dispatchEvent(new StorageEvent("storage", {
      key,
      oldValue,
      newValue,
      storageArea: localStorage,
    }));
  });
}

beforeEach(() => {
  localStorage.clear();
  media = new MockMediaQueryList();
  vi.stubGlobal("matchMedia", vi.fn(() => media));
  themeColor = document.createElement("meta");
  themeColor.name = "theme-color";
  document.head.append(themeColor);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.themePreference;
  themeColor.remove();
});

describe("theme bootstrap", () => {
  it.each([
    ["light", true],
    ["dark", false],
  ] as const)("preserves saved %s over an opposite system preference", (saved, systemDark) => {
    localStorage.setItem("theme", saved);
    media.matches = systemDark;

    bootstrap();

    expectTheme(saved, saved);
    render(<ThemeToggle />);
    expect(toggleButton(saved)).toBeTruthy();
    expectTheme(saved, saved);
    expect(localStorage.getItem("theme")).toBe(saved);
  });

  it.each([
    [null, false, "light"],
    [null, true, "dark"],
    ["invalid", false, "light"],
    ["invalid", true, "dark"],
  ] as const)("uses the system for stored %s and dark=%s", (saved, systemDark, expected) => {
    if (saved !== null) localStorage.setItem("theme", saved);
    media.matches = systemDark;

    bootstrap();

    expectTheme(expected, "system");
  });

  it("falls back to light when matchMedia is unavailable", () => {
    vi.stubGlobal("matchMedia", undefined);

    bootstrap();

    expectTheme("light", "system");
    render(<ThemeToggle />);
    fireEvent.click(toggleButton("light"));
    expectTheme("dark", "dark");
  });
});

describe("ThemeToggle", () => {
  it("persists both selections and updates the accessible action name", () => {
    bootstrap();
    render(<ThemeToggle />);

    fireEvent.click(toggleButton("light"));

    expectTheme("dark", "dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(toggleButton("dark")).toBeTruthy();

    fireEvent.click(toggleButton("dark"));

    expectTheme("light", "light");
    expect(localStorage.getItem("theme")).toBe("light");
    expect(toggleButton("light")).toBeTruthy();
  });

  it("keeps the toggle usable when storage reads and writes throw", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Storage is blocked", "SecurityError");
    });
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Storage is full", "QuotaExceededError");
    });
    media.matches = true;

    expect(bootstrap).not.toThrow();
    expectTheme("dark", "system");
    render(<ThemeToggle />);

    fireEvent.click(toggleButton("dark"));

    expectTheme("light", "light");
    expect(toggleButton("light")).toBeTruthy();
    expect(write).toHaveBeenLastCalledWith("theme", "light");

    act(() => media.change(false));
    act(() => media.change(true));
    expectTheme("light", "light");

    fireEvent.click(toggleButton("light"));
    expectTheme("dark", "dark");
    expect(toggleButton("dark")).toBeTruthy();
  });

  it("follows system changes in both directions without saving a manual choice", () => {
    bootstrap();
    render(<ThemeToggle />);

    act(() => media.change(true));
    expectTheme("dark", "system");
    expect(toggleButton("dark")).toBeTruthy();

    act(() => media.change(false));
    expectTheme("light", "system");
    expect(toggleButton("light")).toBeTruthy();
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it.each(["light", "dark"] as const)("does not override manual %s on a system change", (saved) => {
    localStorage.setItem("theme", saved);
    media.matches = saved === "dark";
    bootstrap();
    render(<ThemeToggle />);

    act(() => media.change(saved !== "dark"));

    expectTheme(saved, saved);
    expect(toggleButton(saved)).toBeTruthy();
  });

  it("synchronizes another tab's dark and light choices", () => {
    bootstrap();
    render(<ThemeToggle />);

    changeStoredTheme("theme", "dark");
    expectTheme("dark", "dark");
    expect(toggleButton("dark")).toBeTruthy();

    changeStoredTheme("theme", "light");
    expectTheme("light", "light");
    expect(toggleButton("light")).toBeTruthy();
  });

  it.each([
    ["theme", null],
    [null, null],
    ["theme", "invalid"],
  ] as const)("resumes system tracking after storage key=%s value=%s", (key, value) => {
    localStorage.setItem("theme", "dark");
    bootstrap();
    render(<ThemeToggle />);

    changeStoredTheme(key, value);

    expectTheme("light", "system");
    expect(toggleButton("light")).toBeTruthy();

    act(() => media.change(true));
    expectTheme("dark", "system");
    expect(toggleButton("dark")).toBeTruthy();
  });

  it("ignores storage changes for unrelated keys", () => {
    localStorage.setItem("theme", "dark");
    bootstrap();
    render(<ThemeToggle />);

    changeStoredTheme("unrelated", "light");

    expectTheme("dark", "dark");
    expect(toggleButton("dark")).toBeTruthy();
  });

  it("removes media and storage listeners on unmount", () => {
    bootstrap();
    const { unmount } = render(<ThemeToggle />);
    unmount();

    act(() => media.change(true));
    expectTheme("light", "system");

    changeStoredTheme("theme", "dark");
    expectTheme("light", "system");
  });
});
