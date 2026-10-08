import Link from "next/link";
import { pageHref } from "@/lib/content";

export function Pagination({
  base,
  page,
  pages,
  query,
}: {
  base: string;
  page: number;
  pages: number;
  query?: string;
}) {
  if (pages <= 1) return null;
  const visible = [...new Set([1, page - 1, page, page + 1, pages])]
    .filter((n) => n >= 1 && n <= pages)
    .sort((a, b) => a - b);
  return (
    <nav aria-label="Страницы публикаций" className="mt-10">
      <ul className="flex flex-wrap items-center gap-2">
        {page > 1 && (
          <li>
            <Link
              className="page-link"
              href={pageHref(base, page - 1, query)}
              rel="prev"
            >
              Назад
            </Link>
          </li>
        )}
        {visible.map((n, index) => (
          <li key={n} className="flex items-center gap-2">
            {index > 0 && n - visible[index - 1] > 1 && (
              <span aria-hidden="true">…</span>
            )}
            <Link
              className="page-link"
              href={pageHref(base, n, query)}
              aria-label={`Страница ${n}`}
              aria-current={page === n ? "page" : undefined}
            >
              {n}
            </Link>
          </li>
        ))}
        {page < pages && (
          <li>
            <Link
              className="page-link"
              href={pageHref(base, page + 1, query)}
              rel="next"
            >
              Далее
            </Link>
          </li>
        )}
      </ul>
    </nav>
  );
}
