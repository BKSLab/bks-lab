import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getCookie, fetchMock } = vi.hoisted(() => ({ getCookie: vi.fn(), fetchMock: vi.fn() }));

vi.mock("next/headers", () => ({ cookies: async () => ({ get: getCookie }) }));
vi.mock("next/navigation", () => ({
  redirect: vi.fn((path: string) => { throw new Error(`REDIRECT:${path}`); }),
  notFound: vi.fn(() => { throw new Error("NOT_FOUND"); }),
}));

import { adminFetch, AdminApiError, requireAdmin } from "@/lib/admin-api";
import { adminContentStatus, adminContentType, adminHref, adminMetric, adminPage, adminPeriod } from "@/lib/admin-api/params";

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  getCookie.mockReset().mockReturnValue({ value: "test-session" });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("API_INTERNAL_URL", "http://backend:8000/");
});

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("private admin data", () => {
  it("only forwards the admin cookie to the internal API with caching and redirects disabled", async () => {
    fetchMock.mockResolvedValue(response({ username: "owner" }));
    await expect(requireAdmin()).resolves.toEqual({ username: "owner" });
    expect(getCookie).toHaveBeenCalledWith("admin_session");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend:8000/api/admin/auth/me");
    expect(init.cache).toBe("no-store");
    expect(init.redirect).toBe("error");
    expect(init.headers).toEqual({ Accept: "application/json", Cookie: "admin_session=test-session" });
    expect(init.signal).toBeDefined();
    expect(init.next).toBeUndefined();
  });

  it("redirects before fetching when no session cookie exists", async () => {
    getCookie.mockReturnValue(undefined);
    await expect(requireAdmin()).rejects.toThrow("REDIRECT:/admin/login");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("redirects on expired sessions for any API request", async () => {
    fetchMock.mockResolvedValue(response({ detail: "Not authenticated" }, 401));
    await expect(adminFetch("/subscribers")).rejects.toThrow("REDIRECT:/admin/login");
  });

  it("maps missing material to the route not-found boundary", async () => {
    fetchMock.mockResolvedValue(response({}, 404));
    await expect(adminFetch("/content/987")).rejects.toThrow("NOT_FOUND");
  });

  it("does not leak upstream bodies into rendered errors", async () => {
    fetchMock.mockResolvedValue(response({ detail: "private-upstream-diagnostic" }, 500));
    const error = await adminFetch("/overview").catch((value: unknown) => value);
    expect(error).toBeInstanceOf(AdminApiError);
    expect((error as AdminApiError).status).toBe(500);
    expect(String(error)).not.toContain("private-upstream-diagnostic");
  });

  it("does not propagate request headers embedded in a network error", async () => {
    fetchMock.mockRejectedValue(new Error("Cookie: admin_session=test-session"));
    const error = await adminFetch("/overview").catch((value: unknown) => value);
    expect(error).toBeInstanceOf(AdminApiError);
    expect((error as Error).message).toBe("Admin API is unavailable");
    expect((error as Error).cause).toBeUndefined();
  });

  it("rejects invalid JSON rather than treating unavailable data as zero", async () => {
    fetchMock.mockResolvedValue(new Response("unavailable", { status: 200 }));
    await expect(adminFetch("/overview")).rejects.toBeInstanceOf(AdminApiError);
  });
});

describe("admin filter URLs", () => {
  it("encodes search terms and preserves filters across pagination", () => {
    const url = adminHref("/admin/content", { type: "note", status: "draft", q: "AI & API", page: 2 });
    const params = new URL(url, "https://example.test").searchParams;
    expect(params.get("q")).toBe("AI & API");
    expect(params.get("status")).toBe("draft");
    expect(params.get("page")).toBe("2");
  });

  it("normalizes invalid and repeated parameters before calling the backend", () => {
    for (const raw of ["-1", "0", "1.5", "Infinity", "99999999999999999999", "wrong"]) expect(adminPage(raw)).toBe(1);
    expect(adminPage(["2", "3"])).toBe(2);
    expect(adminPeriod("other")).toBe("30d");
    expect(adminMetric("other")).toBe("views");
    expect(adminContentType("admin")).toBe("");
    expect(adminContentStatus("private")).toBe("");
  });
});
