import type { Metadata } from "next";

export const ARTICLE_PAGE_SIZE = 3;
export const NOTE_PAGE_SIZE = 3;
export const CATEGORY_TITLES: Record<string, string> = {
  development: "Разработка",
  ai: "AI",
  management: "Управление",
  thoughts: "Мысли",
  accessibility: "Инклюзия",
};

export function formatDate(date: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(date));
}

export function pageNumber(value: string): number | null {
  if (!/^[1-9]\d*$/.test(value)) return null;
  const page = Number(value);
  return Number.isSafeInteger(page) ? page : null;
}

export function pageHref(base: string, page: number, query?: string) {
  if (query) {
    const params = new URLSearchParams({ q: query });
    if (page > 1) params.set("page", String(page));
    return `${base}?${params}`;
  }
  return page === 1 ? base : `${base}/page/${page}`;
}

export function pageMetadata(
  title: string,
  description: string,
  path: string,
  image = "/og/bks-lab-default.jpg",
): Metadata {
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title: `${title} — BKS Lab`,
      description,
      url: path,
      siteName: "BKS Lab",
      locale: "ru_RU",
      type: "website",
      images: [{ url: image, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} — BKS Lab`,
      description,
      images: [image],
    },
  };
}

export function absoluteUrl(path: string) {
  return new URL(
    path,
    process.env.SITE_URL ?? "http://localhost:3000",
  ).toString();
}

export function serializeJsonLd(data: unknown) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
