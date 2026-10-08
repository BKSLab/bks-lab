import Link from "next/link";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin/AdminShell";

const sections = [
  { key: "items", href: "/admin/news/items", label: "Подборки" },
  { key: "sources", href: "/admin/news/sources", label: "Источники" },
  { key: "topics", href: "/admin/news/topics", label: "Темы и рубрики" },
  { key: "runs", href: "/admin/news/runs", label: "Запуски" },
  { key: "settings", href: "/admin/news/settings", label: "Настройки" },
] as const;

export function NewsShell({ username, current, title, description, children }: {
  username: string; current: typeof sections[number]["key"]; title: string; description?: string; children: ReactNode;
}) {
  return <AdminShell username={username} current="news">
    <header className="admin-heading"><p className="news-eyebrow">Редакционный центр</p><h1>{title}</h1>{description && <p className="admin-muted">{description}</p>}</header>
    <nav aria-label="Редакционный центр"><ul className="admin-nav news-nav">{sections.map(section => <li key={section.key}>
      <Link prefetch={false} href={section.href} aria-current={current === section.key ? "page" : undefined}>{section.label}</Link>
    </li>)}</ul></nav>
    {children}
  </AdminShell>;
}
