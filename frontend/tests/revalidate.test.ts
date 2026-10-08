import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn(), revalidateTag: vi.fn() }));
import { revalidatePath, revalidateTag } from "next/cache";
import { POST } from "@/app/api/revalidate/route";

const secret = "test-revalidation-secret-with-at-least-32-characters";
beforeEach(() => { vi.clearAllMocks(); vi.stubEnv("REVALIDATE_SECRET", secret); });
afterEach(() => vi.unstubAllEnvs());

describe("content publication webhook", () => {
  it.each([undefined, "", "short"])("fails closed when configuration is %s", async (value) => {
    vi.stubEnv("REVALIDATE_SECRET", value);
    const response = await POST(new Request("http://localhost/api/revalidate", { method: "POST" }));
    expect(response.status).toBe(503);
    expect(revalidateTag).not.toHaveBeenCalled();
  });

  it.each([undefined, "Bearer wrong", `Basic ${secret}`])("rejects missing or invalid authentication", async (authorization) => {
    const response = await POST(new Request(`http://localhost/api/revalidate?secret=${secret}`, {
      method: "POST", headers: authorization ? { authorization } : {},
    }));
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("expires content and route caches with an authenticated request", async () => {
    const response = await POST(new Request("http://localhost/api/revalidate", {
      method: "POST", headers: { authorization: `Bearer ${secret}` },
    }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ revalidated: true });
    expect(revalidateTag).toHaveBeenCalledTimes(3);
    for (const tag of ["articles", "notes", "projects"]) expect(revalidateTag).toHaveBeenCalledWith(tag, { expire: 0 });
    expect(revalidatePath).toHaveBeenCalledWith("/", "layout");
    expect(revalidatePath).toHaveBeenCalledWith("/sitemap.xml");
  });
});
