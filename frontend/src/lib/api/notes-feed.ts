import type { NotesFeedPage } from "./types";

export type NotesFeedParams = { limit?: number } & (
  | { before?: string; after?: never }
  | { after?: string; before?: never }
);

export function notesFeedPath(params: NotesFeedParams = {}) {
  const search = new URLSearchParams({ limit: String(params.limit ?? 20) });
  if (params.before) search.set("before", params.before);
  if (params.after) search.set("after", params.after);
  return `/notes/feed?${search}`;
}

/** Public requests never carry an admin session or reuse cached feed responses. */
export async function fetchNotesFeed(
  params: NotesFeedParams,
  signal?: AbortSignal,
): Promise<NotesFeedPage> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", cancel, { once: true });
  const timeout = setTimeout(cancel, 5000);
  try {
    const response = await fetch(`/api/v1${notesFeedPath(params)}`, {
      cache: "no-store",
      credentials: "omit",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Notes feed request failed");
    return (await response.json()) as NotesFeedPage;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", cancel);
  }
}
