import { notFound } from "next/navigation";
import { Container } from "@/components/layout/Container";
import { Breadcrumbs } from "./Breadcrumbs";
import { NoteAnchorFocus } from "./NoteAnchorFocus";
import { NoteEntry } from "./NoteEntry";
import { NotesFeed } from "./NotesFeed";
import { Pagination } from "./Pagination";
import { getNotes, getNotesFeed } from "@/lib/api";
import { NOTE_PAGE_SIZE, pageHref, pageMetadata } from "@/lib/content";

export function notesMetadata(page = 1) {
  return pageMetadata(
    `Заметки${page > 1 ? ` — страница ${page}` : ""}`,
    `Короткие заметки на полях: наблюдения о разработке, управлении и технологиях.${page > 1 ? ` Страница ${page}.` : ""}`,
    pageHref("/notes", page),
  );
}

export async function NotesPageContent({ page = 1 }: { page?: number }) {
  const [notes, feed] = await Promise.all([
    getNotes({ page, pageSize: NOTE_PAGE_SIZE }),
    page === 1 ? getNotesFeed({ limit: NOTE_PAGE_SIZE }) : Promise.resolve(null),
  ]);
  if (page > 1 && page > notes.pages) notFound();
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs
        items={
          page > 1
            ? [
                { title: "Заметки", href: "/notes" },
                { title: `Страница ${page}` },
              ]
            : [{ title: "Заметки" }]
        }
      />
      <div className="mx-auto max-w-[72ch]">
        <header className="mb-8">
          <p className="eyebrow mb-4">КОРОТКО / ПО ДЕЛУ / НА ПОЛЯХ</p>
          <h1 className="page-title">
            Заметки на полях
            {page > 1 && (
              <span className="mt-3 block text-xl font-normal text-text-muted">
                Страница {page}
              </span>
            )}
          </h1>
          <p className="mt-5 text-text-muted">
            Наблюдения о разработке, управлении и технологиях. Иногда для важной
            мысли достаточно нескольких строк.
          </p>
        </header>
        {feed ? (
          <NotesFeed initialFeed={feed} />
        ) : (
          <div>
            {notes.items.map((note) => <NoteEntry key={note.slug} note={note} />)}
            {!notes.items.length && <p className="empty-state">Заметки скоро появятся.</p>}
            <NoteAnchorFocus />
          </div>
        )}
        <Pagination base="/notes" page={page} pages={notes.pages} />
      </div>
    </Container>
  );
}
