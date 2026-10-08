import Image from "next/image";
import Link from "next/link";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { ArticleMeta, Tags } from "@/components/content/Cards";
import { ContentHtml } from "@/components/content/ContentHtml";
import { Container } from "@/components/layout/Container";
import { AdSlot } from "@/components/ads/AdSlot";
import { getArticle, getArticles } from "@/lib/api";
import {
  absoluteUrl,
  CATEGORY_TITLES,
  pageMetadata,
  serializeJsonLd,
} from "@/lib/content";

export const revalidate = 300;
export const dynamicParams = true;
type Props = { params: Promise<{ slug: string }> };

export async function generateStaticParams() {
  const first = await getArticles({ pageSize: 50 });
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, first.pages - 1) }, (_, i) =>
      getArticles({ page: i + 2, pageSize: 50 }),
    ),
  );
  return [first, ...rest].flatMap((data) =>
    data.items.map((item) => ({ slug: item.slug })),
  );
}

export async function generateMetadata({ params }: Props) {
  const article = await getArticle((await params).slug);
  const meta = pageMetadata(
    article.seo.title || article.title,
    article.seo.description || article.excerpt,
    `/blog/post/${article.slug}`,
    article.seo.og_image || "/og/bks-lab-default.jpg",
  );
  return {
    ...meta,
    openGraph: {
      ...meta.openGraph,
      type: "article",
      publishedTime: article.published_at,
      authors: ["BKS Lab"],
      tags: article.tags,
    },
  };
}

export default async function ArticlePage({ params }: Props) {
  const article = await getArticle((await params).slug);
  const category = CATEGORY_TITLES[article.category] ?? article.category;
  const path = `/blog/post/${article.slug}`;
  const structuredData = [
    {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: article.title,
      description: article.excerpt,
      datePublished: article.published_at,
      image: absoluteUrl(article.cover_image),
      mainEntityOfPage: absoluteUrl(path),
      author: {
        "@type": "Person",
        name: "BKS Lab",
        url: absoluteUrl("/about"),
      },
      publisher: { "@type": "Organization", name: "BKS Lab" },
      inLanguage: "ru-RU",
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { title: "BKS Lab", path: "/" },
        { title: "Блог", path: "/blog" },
        { title: category, path: `/blog/${article.category}` },
        { title: article.title, path },
      ].map((item, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: item.title,
        item: absoluteUrl(item.path),
      })),
    },
  ];
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs
        items={[
          { title: "Блог", href: "/blog" },
          { title: category, href: `/blog/${article.category}` },
          { title: article.title },
        ]}
      />
      <article className="mx-auto max-w-[72ch]">
        <header className="mb-10">
          <Link
            className="eyebrow inline-flex min-h-11 items-center hover:underline"
            href={`/blog/${article.category}`}
          >
            {category}
          </Link>
          <h1 className="page-title my-5">{article.title}</h1>
          <ArticleMeta article={article} />
          <p className="mt-6 text-xl text-text-muted">{article.excerpt}</p>
          <div className="mt-6">
            <Tags tags={article.tags} />
          </div>
        </header>
        <Image
          src={article.cover_image}
          alt=""
          width={1200}
          height={750}
          sizes="(min-width: 1100px) 800px, 100vw"
          className="mb-10 h-auto w-full rounded-card"
        />
        <ContentHtml html={article.content_html} />
        <footer className="mt-12 border-t border-border pt-6">
          <Link href={`/blog/${article.category}`} className="text-link">
            Ещё о теме «{category}» →
          </Link>
        </footer>
      </article>
      <AdSlot placement="article-end" height={328} className="mx-auto mt-12 max-w-[72ch]" />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(structuredData) }}
      />
    </Container>
  );
}
