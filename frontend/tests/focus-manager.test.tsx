import { StrictMode } from "react";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigationState = {
  pathname: "/",
  searchParams: new URLSearchParams(),
};

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useSearchParams: () => navigationState.searchParams,
}));

import { FocusManager } from "@/components/tracking/FocusManager";

function commitUrl(url: string) {
  window.history.replaceState(null, "", url);
  navigationState.pathname = window.location.pathname;
  navigationState.searchParams = new URLSearchParams(window.location.search);
}

function Page() {
  return (
    <>
      <a id="outside-main" href="/notes">Открыть заметки</a>
      <main id="main-content">
        <h1>{navigationState.pathname === "/" ? "Главная" : "Заметки"}</h1>
        <article id="note-first">Первая заметка</article>
        <article id="note-вторая">Вторая заметка</article>
        <section hidden>
          <article id="hidden-note">Скрытая заметка</article>
        </section>
        <section style={{ display: "none" }}>
          <article id="css-hidden-note">Ещё одна скрытая заметка</article>
        </section>
        <button id="disabled-target" disabled>Недоступная кнопка</button>
      </main>
      <FocusManager />
    </>
  );
}

beforeEach(() => {
  commitUrl("/");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FocusManager", () => {
  it("leaves initial deep-link focus alone, including StrictMode replay", () => {
    commitUrl("/notes#note-first");
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    const { rerender } = render(<StrictMode><Page /></StrictMode>);
    rerender(<StrictMode><Page /></StrictMode>);

    expect(focus).not.toHaveBeenCalled();
  });

  it("moves a client route transition to H1 without resetting restored scroll", () => {
    const { rerender } = render(<Page />);
    screen.getByRole("link").focus();
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    commitUrl("/notes");
    rerender(<Page />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(document.activeElement).toBe(heading);
    expect(heading.getAttribute("tabindex")).toBe("-1");
    expect(focus).toHaveBeenLastCalledWith({ preventScroll: true });
  });

  it("focuses a decoded content anchor after a route transition", () => {
    const { rerender } = render(<Page />);
    screen.getByRole("link").focus();
    commitUrl("/notes#note-%D0%B2%D1%82%D0%BE%D1%80%D0%B0%D1%8F");
    rerender(<Page />);

    expect(document.activeElement).toBe(document.getElementById("note-вторая"));
    expect(document.activeElement?.getAttribute("tabindex")).toBe("-1");
  });

  it.each([
    "missing",
    "%E0%A4%A",
    "hidden-note",
    "css-hidden-note",
    "disabled-target",
    "outside-main",
  ])("falls back to H1 when #%s is not an available content target", (hash) => {
    const { rerender } = render(<Page />);
    screen.getByRole("link").focus();
    commitUrl(`/notes#${hash}`);
    rerender(<Page />);

    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1 }));
  });

  it("handles a native hash change once without refocusing on duplicate events", () => {
    commitUrl("/notes");
    render(<Page />);

    act(() => {
      window.history.replaceState(null, "", "/notes#note-first");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(document.activeElement).toBe(document.getElementById("note-first"));

    const link = screen.getByRole("link");
    link.focus();
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    expect(document.activeElement).toBe(link);
  });

  it("handles a router hash-only commit with unchanged pathname and query", () => {
    commitUrl("/notes");
    const { rerender } = render(<Page />);
    commitUrl("/notes#note-first");
    rerender(<Page />);

    expect(document.activeElement).toBe(document.getElementById("note-first"));
  });

  it("does not steal focus when only search parameters change", () => {
    commitUrl("/notes");
    const { rerender } = render(<Page />);
    const link = screen.getByRole("link");
    link.focus();
    commitUrl("/notes?q=typescript");
    rerender(<Page />);

    expect(document.activeElement).toBe(link);
  });

  it("handles fragment Back/Forward and falls back to H1 when the hash clears", () => {
    commitUrl("/notes#note-first");
    render(<Page />);

    act(() => {
      window.history.replaceState(null, "", "/notes#note-%D0%B2%D1%82%D0%BE%D1%80%D0%B0%D1%8F");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(document.activeElement).toBe(document.getElementById("note-вторая"));

    act(() => {
      window.history.replaceState(null, "", "/notes");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1 }));
  });

  it("waits for the destination DOM when history changes the route before React commits", () => {
    const { rerender } = render(<Page />);
    const link = screen.getByRole("link");
    link.focus();

    act(() => {
      window.history.replaceState(null, "", "/notes#note-first");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(document.activeElement).toBe(link);

    navigationState.pathname = "/notes";
    rerender(<Page />);
    expect(document.activeElement).toBe(document.getElementById("note-first"));
  });
});
