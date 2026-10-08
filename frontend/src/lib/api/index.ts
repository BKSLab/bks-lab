import { notFound } from "next/navigation";

import type {
  ArticleDetail,
  ArticleSummary,
  Category,
  Note,
  Paged,
  ProjectDetail,
  ProjectSummary,
} from "./types";

export const API_TIMEOUT_MS = 5000;
export const API_REVALIDATE_SECONDS = 300;

export class ApiError extends Error {
  /** HTTP status, or null when the request never got a response
   *  (network failure or timeout). */
  readonly status: number | null;
  readonly timedOut: boolean;

  constructor(
    message: string,
    options: { status?: number | null; timedOut?: boolean; cause?: unknown } = {},
  ) {
    super(message, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status ?? null;
    this.timedOut = options.timedOut ?? false;
  }
}

export class ApiNotFoundError extends ApiError {
  constructor(path: string) {
    super(`API resource not found: ${path}`, { status: 404 });
    this.name = "ApiNotFoundError";
  }
}

/** True when the API could not be reached at all (network error, timeout).
 *  Used for the build-time graceful fallback (docs/architecture.md section 4). */
export function isApiUnavailable(error: unknown): boolean {
  return error instanceof ApiError && error.status === null;
}

interface ApiFetchOptions {
  tags: string[];
  revalidate?: number;
  timeoutMs?: number;
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions,
): Promise<T> {
  const {
    tags,
    revalidate = API_REVALIDATE_SECONDS,
    timeoutMs = API_TIMEOUT_MS,
  } = options;
  const isServer = typeof window === "undefined";
  const base =
    process.env.API_INTERNAL_URL ??
    (isServer ? "http://localhost:8000" : "");
  const url = `${base}/api/v1${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      signal: AbortSignal.timeout(timeoutMs),
      next: { revalidate, tags },
    });
  } catch (error) {
    const timedOut =
      error instanceof DOMException &&
      (error.name === "TimeoutError" || error.name === "AbortError");
    throw new ApiError(
      timedOut
        ? `API request timed out after ${timeoutMs} ms: ${path}`
        : `API request failed: ${path}`,
      { timedOut, cause: error },
    );
  }

  if (response.status === 404) {
    throw new ApiNotFoundError(path);
  }
  if (!response.ok) {
    throw new ApiError(`API responded with ${response.status}: ${path}`, {
      status: response.status,
    });
  }
  return (await response.json()) as T;
}

async function withUnavailableFallback<T>(
  request: Promise<T>,
  fallback: T,
): Promise<T> {
  try {
    return await request;
  } catch (error) {
    if (
      isApiUnavailable(error) &&
      process.env.NEXT_PHASE === "phase-production-build"
    ) {
      return fallback;
    }
    throw error;
  }
}

function emptyPaged<T>(page = 1, pageSize = 10): Paged<T> {
  return { items: [], total: 0, page, page_size: pageSize, pages: 0 };
}

export interface ListArticlesParams {
  page?: number;
  pageSize?: number;
  category?: string;
  q?: string;
}

export async function getArticles(
  params: ListArticlesParams = {},
): Promise<Paged<ArticleSummary>> {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.pageSize) search.set("page_size", String(params.pageSize));
  if (params.category) search.set("category", params.category);
  if (params.q) search.set("q", params.q);
  const suffix = search.size > 0 ? `?${search.toString()}` : "";

  return withUnavailableFallback(
    apiFetch<Paged<ArticleSummary>>(`/articles${suffix}`, {
      tags: ["articles"],
    }),
    emptyPaged(params.page, params.pageSize),
  );
}

export async function getLatestArticles(limit = 3): Promise<ArticleSummary[]> {
  return withUnavailableFallback(
    apiFetch<ArticleSummary[]>(`/articles/latest?limit=${limit}`, {
      tags: ["articles"],
    }),
    [],
  );
}

export async function getArticle(slug: string): Promise<ArticleDetail> {
  try {
    return await apiFetch<ArticleDetail>(`/articles/${slug}`, {
      tags: ["articles"],
    });
  } catch (error) {
    if (error instanceof ApiNotFoundError) {
      notFound();
    }
    throw error;
  }
}

export interface ListNotesParams {
  page?: number;
  pageSize?: number;
}

export async function getNotes(
  params: ListNotesParams = {},
): Promise<Paged<Note>> {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.pageSize) search.set("page_size", String(params.pageSize));
  const suffix = search.size > 0 ? `?${search.toString()}` : "";

  return withUnavailableFallback(
    apiFetch<Paged<Note>>(`/notes${suffix}`, { tags: ["notes"] }),
    emptyPaged(params.page, params.pageSize ?? 20),
  );
}

export async function getLatestNotes(limit = 3): Promise<Note[]> {
  return withUnavailableFallback(
    apiFetch<Note[]>(`/notes/latest?limit=${limit}`, { tags: ["notes"] }),
    [],
  );
}

export async function getCategories(): Promise<Category[]> {
  return withUnavailableFallback(
    apiFetch<Category[]>("/categories", { tags: ["articles"] }),
    [],
  );
}

export async function getProjects(
  params: { featured?: boolean } = {},
): Promise<ProjectSummary[]> {
  const suffix =
    params.featured === undefined ? "" : `?featured=${params.featured}`;
  return withUnavailableFallback(
    apiFetch<ProjectSummary[]>(`/projects${suffix}`, { tags: ["projects"] }),
    [],
  );
}

export async function getProject(slug: string): Promise<ProjectDetail> {
  try {
    return await apiFetch<ProjectDetail>(`/projects/${slug}`, {
      tags: ["projects"],
    });
  } catch (error) {
    if (error instanceof ApiNotFoundError) {
      notFound();
    }
    throw error;
  }
}
