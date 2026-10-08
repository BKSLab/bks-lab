export interface NavItem {
  href: string;
  label: string;
}

// Main navigation order per the design spec (section 9), with the owner-approved
// "Заметки" section added after "Блог" (see docs/architecture.md section 4).
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Главная" },
  { href: "/blog", label: "Блог" },
  { href: "/notes", label: "Заметки" },
  { href: "/projects", label: "Проекты" },
  { href: "/about", label: "Обо мне" },
  { href: "/contacts", label: "Контакты" },
] as const;

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
