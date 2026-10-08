import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";

import type { AdminUser } from "./types";

export class AdminApiError extends Error {
  readonly status: number | null;

  constructor(status: number | null = null) {
    // Do not include upstream bodies, credentials or request headers in errors.
    super("Admin API is unavailable");
    this.name = "AdminApiError";
    this.status = status;
  }
}

/** Server-only through next/headers. Authenticated responses are never cached. */
export async function adminFetch<T>(path: string): Promise<T> {
  const session = (await cookies()).get("admin_session");
  if (!session?.value) redirect("/admin/login");

  const base = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  let response: Response;
  try {
    response = await fetch(`${base}/api/admin${path}`, {
      cache: "no-store",
      redirect: "error",
      headers: {
        Accept: "application/json",
        Cookie: `admin_session=${encodeURIComponent(session.value)}`,
      },
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new AdminApiError();
  }

  if (response.status === 401) redirect("/admin/login");
  if (response.status === 404) notFound();
  if (!response.ok) throw new AdminApiError(response.status);

  try {
    return (await response.json()) as T;
  } catch {
    throw new AdminApiError(response.status);
  }
}

/** Call from every protected page; a layout alone does not secure navigation. */
export function requireAdmin(): Promise<AdminUser> {
  return adminFetch<AdminUser>("/auth/me");
}
