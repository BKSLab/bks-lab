"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, isActivePath } from "@/lib/constants";

interface MainNavigationProps {
  className?: string;
  onNavigate?: () => void;
}

export function MainNavigation({ className, onNavigate }: MainNavigationProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="Основная навигация" className={className}>
      <ul className="flex flex-wrap items-center gap-1">
        {NAV_ITEMS.map((item) => {
          const active = isActivePath(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={onNavigate}
                className={`inline-flex min-h-11 items-center rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "text-accent underline decoration-2 underline-offset-8"
                    : "text-text-muted hover:text-text"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
