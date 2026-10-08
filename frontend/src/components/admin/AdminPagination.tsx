import Link from "next/link";

import { adminHref, adminNumber } from "@/lib/admin-api/params";

export function AdminPagination({ path, page, pages, total, params = {} }: {
  path: string;
  page: number;
  pages: number;
  total: number;
  params?: Record<string, string | number>;
}) {
  const href = (target: number) => adminHref(path, { ...params, page: target });
  return (
    <nav className="admin-pagination" aria-label="Страницы результатов">
      <p className="admin-muted">Всего: {adminNumber(total)}. Страница {page}{pages > 0 ? ` из ${pages}` : ""}.</p>
      <div className="admin-pagination-links">
        {page > 1 && <Link className="admin-button" prefetch={false} href={href(page - 1)}>Назад</Link>}
        {page > pages && page > 1 && <Link className="admin-button" prefetch={false} href={href(1)}>На первую</Link>}
        {page < pages && <Link className="admin-button" prefetch={false} href={href(page + 1)}>Вперёд</Link>}
      </div>
    </nav>
  );
}
