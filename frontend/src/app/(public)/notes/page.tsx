import {
  NotesPageContent,
  notesMetadata,
} from "@/components/content/NotesPageContent";

export const revalidate = 300;
export const metadata = notesMetadata();

export default function NotesPage() {
  return <NotesPageContent />;
}
