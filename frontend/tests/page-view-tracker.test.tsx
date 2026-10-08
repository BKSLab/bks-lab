import { StrictMode } from "react";
import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigationState = {
  pathname: "/",
  searchParams: new URLSearchParams(),
};

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useSearchParams: () => navigationState.searchParams,
}));

let PageViewTracker: typeof import("@/components/tracking/PageViewTracker").PageViewTracker;

const sendBeacon = vi.fn();

beforeEach(async () => {
  // Each test gets a fresh client module, as a newly loaded document does.
  vi.resetModules();
  ({ PageViewTracker } = await import("@/components/tracking/PageViewTracker"));
  sendBeacon.mockReset();
  Object.defineProperty(navigator, "sendBeacon", {
    value: sendBeacon,
    configurable: true,
    writable: true,
  });
  navigationState.pathname = "/";
  navigationState.searchParams = new URLSearchParams();
  window.location.hash = "";
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function beaconBody(call: number): Promise<Record<string, unknown>> {
  const [url, blob] = sendBeacon.mock.calls[call] as [string, Blob];
  expect(url).toBe("/api/v1/stats/pageview");
  expect(blob.type).toBe("application/json");
  return JSON.parse(await blob.text());
}

describe("PageViewTracker", () => {
  it("sends one beacon with the current path as a JSON blob", async () => {
    navigationState.pathname = "/blog";
    render(<PageViewTracker />);

    expect(sendBeacon).toHaveBeenCalledTimes(1);
    expect(await beaconBody(0)).toEqual({ path: "/blog" });
  });

  it("omits an empty referrer", async () => {
    render(<PageViewTracker />);
    const body = await beaconBody(0);
    expect("referrer" in body).toBe(false);
  });

  it("sends a non-empty referrer once across public tracker unmounts and remounts", async () => {
    vi.spyOn(document, "referrer", "get").mockReturnValue(
      "https://search.example/results",
    );
    navigationState.pathname = "/blog";
    const initial = render(<StrictMode><PageViewTracker /></StrictMode>);
    expect(await beaconBody(0)).toEqual({
      path: "/blog",
      referrer: "https://search.example/results",
    });

    navigationState.pathname = "/notes";
    initial.rerender(<StrictMode><PageViewTracker /></StrictMode>);
    expect(await beaconBody(1)).toEqual({ path: "/notes" });
    initial.unmount();

    navigationState.pathname = "/audit-missing";
    const missing = render(<StrictMode><PageViewTracker /></StrictMode>);
    expect(await beaconBody(2)).toEqual({ path: "/audit-missing" });
    missing.unmount();

    navigationState.pathname = "/blog";
    render(<StrictMode><PageViewTracker /></StrictMode>);
    expect(await beaconBody(3)).toEqual({ path: "/blog" });
    expect(sendBeacon).toHaveBeenCalledTimes(4);
  });

  it("includes query string and location hash in the path", async () => {
    navigationState.pathname = "/notes";
    navigationState.searchParams = new URLSearchParams("page=2");
    window.location.hash = "note-small-team-deploys";
    render(<PageViewTracker />);

    expect(await beaconBody(0)).toEqual({
      path: "/notes?page=2#note-small-team-deploys",
    });
  });

  it("deduplicates the StrictMode double effect and re-renders", async () => {
    const { rerender } = render(
      <StrictMode>
        <PageViewTracker />
      </StrictMode>,
    );
    rerender(
      <StrictMode>
        <PageViewTracker />
      </StrictMode>,
    );

    expect(sendBeacon).toHaveBeenCalledTimes(1);
  });

  it("sends a new beacon when the pathname changes", () => {
    const { rerender } = render(<PageViewTracker />);
    navigationState.pathname = "/projects";
    rerender(<PageViewTracker />);

    expect(sendBeacon).toHaveBeenCalledTimes(2);
  });

  it("does not count hash-only navigation as a new pageview", () => {
    navigationState.pathname = "/notes";
    const { rerender } = render(<PageViewTracker />);
    window.location.hash = "note-small-team-deploys";
    navigationState.searchParams = new URLSearchParams();
    rerender(<PageViewTracker />);

    expect(sendBeacon).toHaveBeenCalledTimes(1);
  });
});
