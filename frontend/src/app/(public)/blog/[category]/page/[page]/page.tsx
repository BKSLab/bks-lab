import { notFound, permanentRedirect } from "next/navigation";
import {
  BlogPageContent,
  blogMetadata,
} from "@/components/blog/BlogPageContent";
import { getCategories } from "@/lib/api";
import { ARTICLE_PAGE_SIZE, CATEGORY_TITLES, pageNumber } from "@/lib/content";

export const revalidate = 300;
export const dynamicParams = true;
type Props = { params: Promise<{ category: string; page: string }> };

export async function generateStaticParams() {
  return (await getCategories()).flatMap((item) =>
    Array.from(
      {
        length: Math.max(
          0,
          Math.ceil(item.articles_count / ARTICLE_PAGE_SIZE) - 1,
        ),
      },
      (_, i) => ({ category: item.slug, page: String(i + 2) }),
    ),
  );
}

export async function generateMetadata({ params }: Props) {
  const { category, page: raw } = await params;
  const page = pageNumber(raw);
  if (!page || !Object.hasOwn(CATEGORY_TITLES, category)) notFound();
  return blogMetadata(page, category);
}

export default async function CategoryPaginatedPage({ params }: Props) {
  const { category, page: raw } = await params;
  const page = pageNumber(raw);
  if (!page || !Object.hasOwn(CATEGORY_TITLES, category)) notFound();
  if (page === 1) permanentRedirect(`/blog/${category}`);
  return <BlogPageContent category={category} page={page} />;
}
