import { notFound, permanentRedirect } from "next/navigation";
import {
  BlogPageContent,
  blogMetadata,
} from "@/components/blog/BlogPageContent";
import { getArticles } from "@/lib/api";
import { ARTICLE_PAGE_SIZE, pageNumber } from "@/lib/content";

export const revalidate = 300;
export const dynamicParams = true;
type Props = { params: Promise<{ page: string }> };

export async function generateStaticParams() {
  const data = await getArticles({ pageSize: ARTICLE_PAGE_SIZE });
  return Array.from({ length: Math.max(0, data.pages - 1) }, (_, i) => ({
    page: String(i + 2),
  }));
}

export async function generateMetadata({ params }: Props) {
  const page = pageNumber((await params).page);
  if (!page) notFound();
  return blogMetadata(page);
}

export default async function BlogPaginatedPage({ params }: Props) {
  const page = pageNumber((await params).page);
  if (!page) notFound();
  if (page === 1) permanentRedirect("/blog");
  return <BlogPageContent page={page} />;
}
