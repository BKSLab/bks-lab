import Image from "next/image";
import Link from "next/link";

import type { ArticleSummary, Note, ProjectSummary } from "@/lib/api/types";
import { CATEGORY_TITLES, formatDate } from "@/lib/content";
import { ArrowRightIcon } from "@/components/ui/icons";

export function Tags({ tags }: { tags: string[] }) {
  return (
    <ul aria-label="Теги" className="flex flex-wrap gap-2">
      {tags.map((tag) => (
        <li
          key={tag}
          className="rounded-full bg-surface-alt px-3 py-1 text-sm text-text-muted"
        >
          {tag}
        </li>
      ))}
    </ul>
  );
}

export function ArticleMeta({
  article,
}: {
  article: Pick<ArticleSummary, "published_at" | "reading_time">;
}) {
  return (
    <p className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-text-muted">
      <time dateTime={article.published_at}>
        {formatDate(article.published_at)}
      </time>
      <span>{article.reading_time} мин чтения</span>
    </p>
  );
}

export function ArticleCard({
  article,
  list = false,
}: {
  article: ArticleSummary;
  list?: boolean;
}) {
  const Heading = list ? "h2" : "h3";
  return (
    <article className={list ? "article-list-item" : "article-card"}>
      <div className="card-image relative overflow-hidden rounded-card bg-surface-alt">
        <Image
          src={article.cover_image}
          alt=""
          fill
          sizes={
            list
              ? "(min-width: 1100px) 240px, (min-width: 768px) 35vw, 100vw"
              : "(min-width: 1100px) 400px, (min-width: 768px) 45vw, 100vw"
          }
          className="object-cover"
        />
      </div>
      <div className="article-card-body">
        <Link
          href={`/blog/${article.category}`}
          className="eyebrow inline-flex min-h-11 items-center hover:underline"
        >
          {CATEGORY_TITLES[article.category] ?? article.category}
        </Link>
        <Heading className="text-xl leading-snug font-semibold">
          <Link
            href={`/blog/post/${article.slug}`}
            className="hover:text-accent hover:underline"
          >
            {article.title}
          </Link>
        </Heading>
        <ArticleMeta article={article} />
        {list && <p className="text-base text-text-muted">{article.excerpt}</p>}
        {list && (
          <Link
            href={`/blog/post/${article.slug}`}
            className="text-link"
            aria-label={`Читать статью: ${article.title}`}
          >
            Читать статью <ArrowRightIcon className="h-4 w-4" />
          </Link>
        )}
      </div>
    </article>
  );
}

export function ProjectCard({
  project,
  heading = "h3",
}: {
  project: ProjectSummary;
  heading?: "h2" | "h3";
}) {
  const Heading = heading;
  return (
    <article className="content-card flex flex-col">
      <div className="card-image relative aspect-[16/10] overflow-hidden rounded-t-card bg-surface-alt">
        <Image
          src={project.cover_image}
          alt=""
          fill
          sizes="(min-width: 1100px) 400px, (min-width: 768px) 45vw, 100vw"
          className="object-cover"
        />
      </div>
      <div className="flex grow flex-col gap-4 p-6">
        <Heading className="text-2xl font-semibold">
          <Link
            href={`/projects/${project.slug}`}
            className="hover:text-accent hover:underline"
          >
            {project.title}
          </Link>
        </Heading>
        {project.status === "archived" && (
          <p className="text-sm text-text-muted">Архивный проект</p>
        )}
        <p className="grow text-base text-text-muted">{project.excerpt}</p>
        <Tags tags={project.tags} />
        <Link
          href={`/projects/${project.slug}`}
          className="text-link self-start"
          aria-label={`О проекте «${project.title}»`}
        >
          О проекте <ArrowRightIcon className="h-4 w-4" />
        </Link>
      </div>
    </article>
  );
}

export function NotePreview({ note }: { note: Note }) {
  return (
    <article className="border-t border-border py-5">
      <time
        dateTime={note.published_at}
        className="font-mono text-sm text-text-muted"
      >
        {formatDate(note.published_at)}
      </time>
      <h3 className="mt-2 text-lg leading-snug font-semibold">
        <Link
          href={`/notes#note-${note.slug}`}
          className="inline-flex min-h-11 items-center hover:text-accent hover:underline"
        >
          {note.title}
        </Link>
      </h3>
      <p className="mt-2 text-base text-text-muted">{note.excerpt}</p>
    </article>
  );
}
