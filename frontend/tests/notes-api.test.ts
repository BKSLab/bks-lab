import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getNotesFeed } from "@/lib/api";
import { fetchNotesFeed, notesFeedPath } from "@/lib/api/notes-feed";

const fetchMock = vi.fn<typeof fetch>();
const empty = { items: [], next_cursor: null, newest_cursor: null, has_more: false };

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset().mockResolvedValue(new Response(JSON.stringify(empty)));
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("public notes feed requests", () => {
  it("encodes opaque cursors without interpreting their content", () => {
    expect(notesFeedPath({ limit: 5, before: "opaque+/= value" })).toBe("/notes/feed?limit=5&before=opaque%2B%2F%3D+value");
    expect(notesFeedPath({ after: "newest" })).toBe("/notes/feed?limit=20&after=newest");
  });

  it("renders the initial feed through the server API with note cache tags", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://backend:8000");
    await expect(getNotesFeed({ limit: 5 })).resolves.toEqual(empty);
    expect(fetchMock).toHaveBeenCalledWith("http://backend:8000/api/v1/notes/feed?limit=5", expect.objectContaining({
      next: { tags: ["notes"], revalidate: 60 },
    }));
  });

  it("loads in the browser without session credentials or stale cache", async () => {
    const controller = new AbortController();
    await expect(fetchNotesFeed({ limit: 20, before: "older" }, controller.signal)).resolves.toEqual(empty);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/notes/feed?limit=20&before=older", expect.objectContaining({
      cache: "no-store", credentials: "omit", signal: expect.any(AbortSignal),
    }));
    expect(controller.signal.aborted).toBe(false);
  });

  it("propagates cancellation and rejects failed responses", async () => {
    const controller = new AbortController();
    fetchMock.mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
      init!.signal!.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const request = fetchNotesFeed({ limit: 20 }, controller.signal);
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
    fetchMock.mockResolvedValueOnce(new Response("", { status: 503 }));
    await expect(fetchNotesFeed({ limit: 20 })).rejects.toThrow("Notes feed request failed");
  });
});
