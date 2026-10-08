import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/layout/Container";
import { AdSlot } from "@/components/ads/AdSlot";
import { Breadcrumbs } from "./Breadcrumbs";
import { ArticleMeta, Tags } from "./Cards";
import { ContentHtml } from "./ContentHtml";
import { NoteAnchorFocus } from "./NoteAnchorFocus";
import { Pagination } from "./Pagination";
import { getNotes } from "@/lib/api";
import { NOTE_PAGE_SIZE, pageHref, pageMetadata } from "@/lib/content";

export function notesMetadata(page = 1) {
  return pageMetadata(
    `Заметки${page > 1 ? ` — страница ${page}` : ""}`,
    `Короткие заметки на полях: наблюдения о разработке, управлении и технологиях.${page > 1 ? ` Страница ${page}.` : ""}`,
    pageHref("/notes", page),
  );
}

export async function NotesPageContent({ page = 1 }: { page?: number }) {
  const notes = await getNotes({ page, pageSize: NOTE_PAGE_SIZE });
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
        <header className="mb-12">
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
        <div className="space-y-10">
          {notes.items.map((note) => (
            <article
              key={note.slug}
              id={`note-${note.slug}`}
              data-note
              tabIndex={-1}
              aria-labelledby={`title-${note.slug}`}
              className="note-entry"
            >
              <ArticleMeta article={note} />
              <h2
                id={`title-${note.slug}`}
                className="my-4 text-2xl font-semibold"
              >
                <a
                  href={`#note-${note.slug}`}
                  className="hover:text-accent hover:underline"
                >
                  {note.title}
                </a>
              </h2>
              <ContentHtml html={note.content_html} />
              <div className="mt-5">
                <Tags tags={note.tags} />
              </div>
              {note.related_article && (
                <p className="mt-5 text-base">
                  <span className="text-text-muted">Подробнее в статье: </span>
                  <Link
                    className="text-accent underline underline-offset-4"
                    href={`/blog/post/${note.related_article.slug}`}
                  >
                    {note.related_article.title}
                  </Link>
                </p>
              )}
            </article>
          ))}
        </div>
        {!notes.items.length && (
          <p className="empty-state">Заметки скоро появятся.</p>
        )}
        <Pagination base="/notes" page={page} pages={notes.pages} />
        <AdSlot placement="notes-feed" height={328} className="mt-10" />
      </div>
      <NoteAnchorFocus />
    </Container>
  );
}
