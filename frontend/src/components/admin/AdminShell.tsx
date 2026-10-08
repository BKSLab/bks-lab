import Link from "next/link";
import type { ReactNode } from "react";

import { AdminLogoutButton } from "./AdminLogoutButton";
import { AdminSessionRefresh } from "./AdminSessionRefresh";

const links = [
  { key: "overview", href: "/admin", label: "Обзор" },
  { key: "pages", href: "/admin/stats/pages", label: "Страницы" },
  { key: "referrers", href: "/admin/stats/referrers", label: "Источники" },
  { key: "content", href: "/admin/content", label: "Материалы" },
  { key: "news", href: "/admin/news", label: "Редакционный центр" },
  { key: "subscribers", href: "/admin/subscribers", label: "Подписчики" },
] as const;

export function AdminShell({ username, current, children }: {
  username: string;
  current: (typeof links)[number]["key"];
  children: ReactNode;
}) {
  return (
    <>
      <AdminSessionRefresh />
      <div className="admin-toolbar">
        <nav aria-label="Разделы панели">
          <ul className="admin-nav">
            {links.map((link) => <li key={link.key}>
              <Link href={link.href} prefetch={false} aria-current={current === link.key ? "page" : undefined}>
                {link.label}
              </Link>
            </li>)}
          </ul>
        </nav>
        <div className="admin-account">
          <span className="admin-muted">{username}</span>
          <AdminLogoutButton />
        </div>
      </div>
      <div className="admin-content">{children}</div>
    </>
  );
}
