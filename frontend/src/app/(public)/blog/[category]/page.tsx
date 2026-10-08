import { notFound } from "next/navigation";
import {
  BlogPageContent,
  blogMetadata,
} from "@/components/blog/BlogPageContent";
import { getCategories } from "@/lib/api";
import { CATEGORY_TITLES } from "@/lib/content";

export const revalidate = 300;
export const dynamicParams = true;
type Props = { params: Promise<{ category: string }> };

export async function generateStaticParams() {
  return (await getCategories()).map((item) => ({ category: item.slug }));
}

export async function generateMetadata({ params }: Props) {
  const { category } = await params;
  if (!Object.hasOwn(CATEGORY_TITLES, category)) notFound();
  return blogMetadata(1, category);
}

export default async function BlogCategoryPage({ params }: Props) {
  const { category } = await params;
  return <BlogPageContent category={category} />;
}
