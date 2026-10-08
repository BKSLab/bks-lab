import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

import { notFound } from "next/navigation";

import {
  ApiError,
  ApiNotFoundError,
  apiFetch,
  getArticle,
  getLatestArticles,
  isApiUnavailable,
} from "@/lib/api";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(notFound).mockClear();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  it("requests the server-side API base with revalidate and tags", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://backend:8000");
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    const result = await apiFetch<{ ok: boolean }>("/articles", {
      tags: ["articles"],
    });

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend:8000/api/v1/articles");
    expect(init.next).toEqual({ revalidate: 300, tags: ["articles"] });
    expect(init.signal).toBeDefined();
  });

  it("rejects with ApiNotFoundError on 404", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));

    await expect(
      apiFetch("/articles/missing", { tags: ["articles"] }),
    ).rejects.toBeInstanceOf(ApiNotFoundError);
  });

  it("rejects with ApiError carrying the status on 5xx", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "boom" }, 500));

    const error = await apiFetch("/articles", { tags: ["articles"] }).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });

  it("maps a timeout to ApiError with timedOut=true and no status", async () => {
    fetchMock.mockRejectedValue(
      new DOMException("The operation timed out", "TimeoutError"),
    );

    const error = await apiFetch("/articles", { tags: ["articles"] }).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).timedOut).toBe(true);
    expect((error as ApiError).status).toBeNull();
    expect(isApiUnavailable(error)).toBe(true);
  });

  it("maps a network failure to ApiError without status", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const error = await apiFetch("/articles", { tags: ["articles"] }).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBeNull();
    expect(isApiUnavailable(error)).toBe(true);
  });
});

describe("getArticle", () => {
  it("calls notFound() when the API answers 404", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));

    await expect(getArticle("missing")).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalledTimes(1);
  });

  it("rethrows server errors instead of calling notFound()", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "boom" }, 500));

    await expect(getArticle("1c-async")).rejects.toBeInstanceOf(ApiError);
    expect(notFound).not.toHaveBeenCalled();
  });
});

describe("graceful fallback when the API is unavailable", () => {
  beforeEach(() => vi.stubEnv("NEXT_PHASE", "phase-production-build"));
  it("returns an empty list on network failure", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    await expect(getLatestArticles(3)).resolves.toEqual([]);
  });

  it("shows an error at runtime instead of silently caching an empty page", async () => {
    vi.stubEnv("NEXT_PHASE", undefined);
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    await expect(getLatestArticles(3)).rejects.toBeInstanceOf(ApiError);
  });

  it("returns an empty list on timeout", async () => {
    fetchMock.mockRejectedValue(
      new DOMException("The operation timed out", "TimeoutError"),
    );

    await expect(getLatestArticles(3)).resolves.toEqual([]);
  });

  it("does not swallow HTTP errors", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "boom" }, 500));

    await expect(getLatestArticles(3)).rejects.toBeInstanceOf(ApiError);
  });
});
