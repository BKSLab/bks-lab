import Link from "next/link";

export interface Crumb {
  title: string;
  href?: string;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Хлебные крошки" className="mb-7 text-sm text-text-muted">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {[{ title: "BKS Lab", href: "/" }, ...items].map((item, index) => (
          <li
            key={`${item.title}-${index}`}
            className="inline-flex items-center gap-2"
          >
            {index > 0 && <span aria-hidden="true">/</span>}
            {item.href ? (
              <Link
                href={item.href}
                className="inline-flex min-h-11 items-center hover:text-accent hover:underline"
              >
                {item.title}
              </Link>
            ) : (
              <span aria-current="page">{item.title}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
