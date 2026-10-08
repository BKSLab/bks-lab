import Link from "next/link";

import { Container } from "@/components/layout/Container";
import { BrandLogo } from "@/components/layout/BrandLogo";
import { NAV_ITEMS } from "@/lib/constants";

export function AppFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border bg-surface">
      <Container className="py-10">
        <div className="grid gap-8 md:grid-cols-3">
          <div>
            <Link
              href="/"
              aria-label="BKS Lab — на главную"
              className="inline-flex min-h-11 items-center"
            >
              <BrandLogo />
            </Link>
            <p className="mt-4 max-w-xs text-sm text-text-muted">
              Разработка. Управление. Искусственный интеллект. Идеи, которые
              работают.
            </p>
          </div>
          <nav aria-label="Разделы сайта">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
              Разделы
            </h2>
            <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
              {NAV_ITEMS.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="inline-flex min-h-11 items-center text-sm text-text-muted hover:text-text md:min-h-0 md:py-1"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label="Дополнительно">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">
              Дополнительно
            </h2>
            <ul className="mt-3 space-y-1">
              <li>
                <Link
                  href="/privacy"
                  className="inline-flex min-h-11 items-center text-sm text-text-muted hover:text-text md:min-h-0 md:py-1"
                >
                  Политика конфиденциальности
                </Link>
              </li>
            </ul>
          </nav>
        </div>
        <p className="mt-10 border-t border-border pt-6 text-sm text-text-muted">
          © {year} BKS Lab. Все права защищены.
        </p>
      </Container>
    </footer>
  );
}
