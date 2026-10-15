import Link from "next/link";

import type { Note } from "@/lib/api/types";
import { formatDate } from "@/lib/content";
import { ContentHtml } from "./ContentHtml";

function sourceUrl(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export function NoteEntry({
  note,
  compact = false,
  preview = false,
}: {
  note: Note;
  compact?: boolean;
  preview?: boolean;
}) {
  const Heading = compact ? "h3" : "h2";
  const originalUrl = sourceUrl(note.source_url);
  const automatic = Boolean(note.source_name || note.source_url);
  const dateTime = note.published_at_time ?? note.published_at;
  const hasTime = note.published_at_time && !Number.isNaN(Date.parse(note.published_at_time));
  const time = hasTime
    ? new Intl.DateTimeFormat("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Europe/Samara",
      }).format(new Date(note.published_at_time!))
    : null;
  return (
    <article
      id={preview ? undefined : `note-${note.slug}`}
      data-note={preview ? undefined : ""}
      tabIndex={preview ? undefined : -1}
      aria-labelledby={`${preview ? "preview" : "title"}-${note.slug}`}
      className={`note-entry${compact ? " note-entry-compact" : ""}`}
    >
      <Heading id={`${preview ? "preview" : "title"}-${note.slug}`} className="note-title">
        <Link
          href={`${preview ? "/notes" : ""}#note-${note.slug}`}
          className="note-title-link"
        >
          {note.title}
        </Link>
      </Heading>
      {automatic || preview ? (
        <p className="note-summary">
          {automatic ? note.excerpt.slice(0, 300) : note.excerpt}
          {originalUrl && (
            <>
              {" "}
              <a
                className="note-details"
                href={originalUrl}
                target="_blank"
                rel="external noopener noreferrer"
                aria-label={`Подробнее… ${note.title} (откроется в новой вкладке)`}
              >
                Подробнее…
              </a>
            </>
          )}
        </p>
      ) : (
        <ContentHtml html={note.content_html} renderAdSlot={() => null} />
      )}
      {!automatic && note.related_article && (
        <p className="note-related">
          Подробнее в статье: {" "}
          <Link href={`/blog/post/${note.related_article.slug}`}>
            {note.related_article.title}
          </Link>
        </p>
      )}
      <p className="note-meta">
        {note.source_name && <span>{note.source_name}</span>}
        <time dateTime={dateTime}>
          {formatDate(note.published_at)}{time ? `, ${time}` : ""}
        </time>
      </p>
    </article>
  );
}
