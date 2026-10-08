import {
  BlogPageContent,
  blogMetadata,
} from "@/components/blog/BlogPageContent";

export const revalidate = 300;
export const metadata = blogMetadata();

export default function BlogPage() {
  return <BlogPageContent />;
}
