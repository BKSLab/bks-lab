import Image from "next/image";
import Link from "next/link";

import type { ArticleSummary } from "@/lib/api/types";
import { formatDate } from "@/lib/content";

export function RelatedArticles({ articles }: { articles: ArticleSummary[] }) {
  if (!articles.length) return null;

  return (
    <section
      aria-labelledby="related-articles-title"
      className="mx-auto mt-12 max-w-[72ch] border-t border-border pt-8"
    >
      <h2 id="related-articles-title" className="mb-4 text-2xl font-semibold">
        Похожие статьи
      </h2>
      <ul className="divide-y divide-border">
        {articles.map((article) => (
          <li key={article.slug}>
            <Link
              href={`/blog/post/${article.slug}`}
              className="group flex min-h-11 min-w-0 items-start gap-4 py-4"
            >
              <Image
                src={article.cover_image}
                alt=""
                width={96}
                height={64}
                sizes="96px"
                className="h-16 w-24 shrink-0 rounded-md object-cover"
              />
              <div className="min-w-0">
                <h3 className="break-words text-lg leading-snug font-semibold group-hover:text-accent group-hover:underline">
                  {article.title}
                </h3>
                <time
                  dateTime={article.published_at}
                  className="mt-2 block text-sm text-text-muted"
                >
                  {formatDate(article.published_at)}
                </time>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
