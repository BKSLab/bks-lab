import { StrictMode } from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const script = vi.hoisted(() => vi.fn<(props: Record<string, unknown>) => null>(() => null));
vi.mock("next/script", () => ({ default: script }));
import { AdSlot } from "@/components/ads/AdSlot";

beforeEach(() => {
  script.mockClear();
  vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "false");
  vi.stubEnv("NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID", "R-A-123456-1");
  vi.stubEnv("NEXT_PUBLIC_YANDEX_AD_ARTICLE_ID", "");
  vi.stubEnv("NEXT_PUBLIC_YANDEX_AD_NOTES_ID", "");
  delete window.Ya;
  delete window.yaContextCb;
});
afterEach(() => { vi.unstubAllEnvs(); delete window.Ya; delete window.yaContextCb; });

describe("advertising slots", () => {
  it("renders nothing and loads no script when disabled", () => {
    const { container } = render(<AdSlot placement="blog-sidebar" />);
    expect(container.childElementCount).toBe(0);
    expect(script).not.toHaveBeenCalled();
    expect(window.yaContextCb).toBeUndefined();
  });

  it.each(["", "placeholder", "<script>"])("loads no script for missing or invalid ID %s", (id) => {
    vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "true");
    vi.stubEnv("NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID", id);
    render(<AdSlot placement="blog-sidebar" />);
    expect(screen.queryByRole("complementary")).toBeNull();
    expect(script).not.toHaveBeenCalled();
  });

  it("reserves a fixed labelled slot and renders through the shared lazy loader", () => {
    vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "true");
    const { container, unmount } = render(<AdSlot placement="blog-sidebar" height={328} />);
    expect(screen.getByRole("complementary", { name: "Реклама" }).style.height).toBe("328px");
    expect(script.mock.calls[0][0]).toMatchObject({ id: "yandex-ad-context", strategy: "lazyOnload", src: "https://yandex.ru/ads/system/context.js" });
    const renderAd = vi.fn();
    const destroy = vi.fn();
    window.Ya = { Context: { AdvManager: { render: renderAd, destroy } } };
    window.yaContextCb?.forEach((callback) => callback());
    expect(renderAd).toHaveBeenCalledWith({ blockId: "R-A-123456-1", renderTo: container.querySelector("div[id]")?.id, darkTheme: false });
    unmount();
    expect(destroy).toHaveBeenCalledWith({ blockId: "R-A-123456-1" });
  });

  it("ignores callbacks after unmount and absorbs StrictMode's effect replay", () => {
    vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "true");
    const first = render(<AdSlot placement="blog-sidebar" />);
    first.unmount();
    render(<StrictMode><AdSlot placement="blog-sidebar" /></StrictMode>);
    const renderAd = vi.fn();
    window.Ya = { Context: { AdvManager: { render: renderAd } } };
    window.yaContextCb?.forEach((callback) => callback());
    expect(renderAd).toHaveBeenCalledOnce();
  });

  it("keeps the page available if the third-party renderer throws", () => {
    vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "true");
    window.Ya = { Context: { AdvManager: { render: () => { throw new Error("provider unavailable"); } } } };
    render(<AdSlot placement="blog-sidebar" height={328} />);
    expect(screen.getByRole("complementary", { name: "Реклама" }).style.height).toBe("328px");
  });
});
