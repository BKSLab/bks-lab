import { notFound, permanentRedirect } from "next/navigation";
import {
  NotesPageContent,
  notesMetadata,
} from "@/components/content/NotesPageContent";
import { getNotes } from "@/lib/api";
import { NOTE_PAGE_SIZE, pageNumber } from "@/lib/content";

export const revalidate = 300;
export const dynamicParams = true;
type Props = { params: Promise<{ page: string }> };

export async function generateStaticParams() {
  const data = await getNotes({ pageSize: NOTE_PAGE_SIZE });
  return Array.from({ length: Math.max(0, data.pages - 1) }, (_, i) => ({
    page: String(i + 2),
  }));
}

export async function generateMetadata({ params }: Props) {
  const page = pageNumber((await params).page);
  if (!page) notFound();
  return notesMetadata(page);
}

export default async function PaginatedNotesPage({ params }: Props) {
  const page = pageNumber((await params).page);
  if (!page) notFound();
  if (page === 1) permanentRedirect("/notes");
  return <NotesPageContent page={page} />;
}
