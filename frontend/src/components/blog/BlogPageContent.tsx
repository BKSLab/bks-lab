import { Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/layout/Container";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { NotePreview } from "@/components/content/Cards";
import { PublicForm } from "@/components/forms/PublicForm";
import { AdSlot } from "@/components/ads/AdSlot";
import { getArticles, getCategories, getLatestNotes } from "@/lib/api";
import {
  ARTICLE_PAGE_SIZE,
  CATEGORY_TITLES,
  pageHref,
  pageMetadata,
} from "@/lib/content";
import { ArticleResults } from "./ArticleResults";
import { BlogSearch } from "./BlogSearch";

export const BLOG_DESCRIPTION =
  "Размышления, опыт и практические материалы о разработке, управлении и искусственном интеллекте.";

export function blogMetadata(page = 1, category?: string) {
  const title = category ? CATEGORY_TITLES[category] : "Блог";
  const description = category
    ? `Статьи BKS Lab на тему «${title}»: опыт, идеи и практические материалы.`
    : BLOG_DESCRIPTION;
  return pageMetadata(
    `${title}${page > 1 ? ` — страница ${page}` : ""}`,
    `${description}${page > 1 ? ` Страница ${page}.` : ""}`,
    pageHref(category ? `/blog/${category}` : "/blog", page),
    "/og/blog.jpg",
  );
}

export async function BlogPageContent({
  page = 1,
  category,
}: {
  page?: number;
  category?: string;
}) {
  if (category && !Object.hasOwn(CATEGORY_TITLES, category)) notFound();
  const [articles, categories, notes] = await Promise.all([
    getArticles({ page, pageSize: ARTICLE_PAGE_SIZE, category }),
    getCategories(),
    getLatestNotes(3),
  ]);
  if (page > 1 && page > articles.pages) notFound();
  const base = category ? `/blog/${category}` : "/blog";
  const title = category ? CATEGORY_TITLES[category] : "Блог";
  const crumbs = [
    ...(category || page > 1 ? [{ title: "Блог", href: "/blog" }] : []),
    ...(category ? [{ title, ...(page > 1 ? { href: base } : {}) }] : []),
    ...(page > 1
      ? [{ title: `Страница ${page}` }]
      : category
        ? []
        : [{ title: "Блог" }]),
  ];
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={crumbs} />
      <section className="blog-hero" aria-labelledby="blog-title">
        <div className="blog-hero-copy">
          <p className="eyebrow mb-4">ОПЫТ / ПРАКТИКА / НАБЛЮДЕНИЯ</p>
          <h1 id="blog-title" className="page-title">
            {title}
            {page > 1 && (
              <span className="mt-3 block text-xl font-normal text-text-muted">
                Страница {page}
              </span>
            )}
          </h1>
          <p className="mt-5 max-w-prose text-text-muted">{BLOG_DESCRIPTION}</p>
        </div>
        <div className="blog-hero-art">
          <Image
            src="/images/blog/blog-hero.webp"
            alt=""
            fill
            sizes="(min-width: 1320px) 600px, (min-width: 768px) 48vw, 100vw"
            className="object-cover"
            loading="eager"
            fetchPriority="high"
          />
        </div>
      </section>
      <nav aria-label="Категории статей" className="my-10">
        <ul className="flex flex-wrap gap-2">
          {[
            { slug: "", title: "Все статьи" },
            ...Object.entries(CATEGORY_TITLES).map(([slug, name]) => ({
              slug,
              title: name,
            })),
          ].map((item) => (
            <li key={item.slug}>
              <Link
                href={item.slug ? `/blog/${item.slug}` : "/blog"}
                className="filter-link"
                aria-current={
                  (category ?? "") === item.slug ? "page" : undefined
                }
              >
                {item.title}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <div className="blog-columns">
        <section aria-label="Статьи" className="min-w-0">
          <Suspense fallback={<ArticleResults data={articles} base={base} />}>
            <BlogSearch initial={articles} base={base} category={category} />
          </Suspense>
        </section>
        <aside
          aria-label="Дополнительно о блоге"
          className="min-w-0 space-y-10"
        >
          <section className="rounded-card border border-border bg-surface p-6">
            <h2 className="mb-4 text-xl font-semibold">Подписка</h2>
            <PublicForm kind="newsletter" />
          </section>
          <section>
            <h2 className="mb-4 text-xl font-semibold">Популярные темы</h2>
            <ul>
              {(categories.length
                ? categories
                : Object.entries(CATEGORY_TITLES).map(([slug, name]) => ({
                    slug,
                    title: name,
                    articles_count: 0,
                  }))
              ).map((item) => (
                <li key={item.slug}>
                  <Link
                    className="flex min-h-11 items-center justify-between gap-3 border-b border-border py-2 hover:text-accent hover:underline"
                    href={`/blog/${item.slug}`}
                  >
                    <span>{item.title}</span>
                    <span className="font-mono text-sm text-text-muted">
                      {item.articles_count}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2 className="mb-4 text-xl font-semibold">Заметки на полях</h2>
            {notes.map((note) => (
              <NotePreview key={note.slug} note={note} />
            ))}
            <Link href="/notes" className="text-link">
              Все заметки →
            </Link>
          </section>
          <blockquote className="border-l-2 border-accent pl-5">
            <p className="text-lg">
              Лучшие решения рождаются на стыке технологий, людей и реальных
              проблем.
            </p>
            <footer className="mt-3 font-mono text-sm text-text-muted">
              — BKS Lab
            </footer>
          </blockquote>
          <AdSlot placement="blog-sidebar" height={328} />
        </aside>
      </div>
    </Container>
  );
}
