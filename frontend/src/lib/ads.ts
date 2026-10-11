export type AdPlacement = "blog-sidebar" | "article-end" | "article-inline" | "notes-feed";

export function adBlockId(placement: AdPlacement): string | undefined {
  if (process.env.NEXT_PUBLIC_ADS_ENABLED !== "true") return undefined;
  const ids = {
    "blog-sidebar": process.env.NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID,
    "article-end": process.env.NEXT_PUBLIC_YANDEX_AD_ARTICLE_ID,
    "article-inline": process.env.NEXT_PUBLIC_YANDEX_AD_INLINE_ID,
    "notes-feed": process.env.NEXT_PUBLIC_YANDEX_AD_NOTES_ID,
  };
  const value = ids[placement]?.trim();
  return value && /^R-[A-Z]-\d+-\d+$/.test(value) ? value : undefined;
}

export function adsConfigured(): boolean {
  return (["blog-sidebar", "article-end", "article-inline", "notes-feed"] as const).some((placement) => Boolean(adBlockId(placement)));
}
