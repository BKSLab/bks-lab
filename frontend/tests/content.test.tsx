import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sanitizeContent } from "@/lib/sanitize";
import { pageHref, pageNumber, serializeJsonLd } from "@/lib/content";
import { Pagination } from "@/components/content/Pagination";

describe("publication safety and URLs", () => {
  it("removes active markup and extra H1 while retaining article structure", () => {
    const html = sanitizeContent(
      '<h1>Extra title</h1><h2>Section</h2><script>alert(1)</script><img src="/safe.webp" onerror="alert(1)" alt="Diagram"><a href="javascript:alert(1)">Link</a><iframe src="https://evil.test"></iframe><form><input name="email"></form><pre><code>const x = 1;</code></pre><table><tr><th scope="col">Name</th></tr></table>',
    );
    const document = new DOMParser().parseFromString(html, "text/html");
    expect(
      document.querySelector("script,iframe,form,input,h1,[onerror],a[href]"),
    ).toBeNull();
    expect(document.querySelector("h2")?.textContent).toBe("Section");
    expect(document.querySelector("code")?.textContent).toBe("const x = 1;");
    expect(document.querySelector("img")?.getAttribute("alt")).toBe("Diagram");
    expect(document.querySelector("th")?.getAttribute("scope")).toBe("col");
  });
  it("escapes JSON-LD script terminators without changing the data", () => {
    const data = { headline: '</script><script>alert("x")</script>' };
    expect(serializeJsonLd(data)).not.toContain("<");
    expect(JSON.parse(serializeJsonLd(data))).toEqual(data);
  });
  it.each(["0", "-1", "1.5", "01", "no", "9007199254740992"])(
    "rejects invalid page %s",
    (value) => {
      expect(pageNumber(value)).toBeNull();
    },
  );
  it("creates indexable paths and preserves search terms in search pagination", () => {
    expect(pageHref("/blog", 1)).toBe("/blog");
    expect(pageHref("/blog", 2)).toBe("/blog/page/2");
    expect(pageHref("/blog/development", 2)).toBe("/blog/development/page/2");
    expect(pageHref("/notes", 2)).toBe("/notes/page/2");
    expect(pageHref("/blog", 2, "AI & code")).toBe(
      "/blog?q=AI+%26+code&page=2",
    );
  });
  it("exposes the current page without rendering hundreds of links", () => {
    render(<Pagination base="/notes" page={50} pages={100} />);
    expect(
      screen
        .getByRole("link", { name: "Страница 50" })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(screen.getAllByRole("link").length).toBeLessThan(10);
    expect(
      screen.getByRole("link", { name: "Далее" }).getAttribute("href"),
    ).toBe("/notes/page/51");
  });
});
