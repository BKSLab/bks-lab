import type { Metadata } from "next";
import Link from "next/link";

import { BrandLogo } from "@/components/layout/BrandLogo";
import { SkipLink } from "@/components/layout/SkipLink";
import { ThemeToggle } from "@/components/navigation/ThemeToggle";
import "./admin.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "Панель сайта — BKS Lab", template: "%s — Панель BKS Lab" },
  description: "Закрытая панель BKS Lab.",
  robots: { index: false, follow: false, noarchive: true },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="admin-root">
      <SkipLink />
      <header className="admin-header">
        <div className="admin-container admin-header-inner">
          <Link href="/" className="admin-brand" aria-label="BKS Lab — на главную"><BrandLogo /></Link>
          <span className="admin-header-label">Панель сайта</span>
          <div className="admin-header-actions">
            <Link href="/" className="admin-link">На сайт</Link>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="admin-container admin-main" id="main-content" tabIndex={-1}>{children}</main>
      <footer className="admin-container admin-footer"><p>BKS Lab · Панель владельца</p></footer>
    </div>
  );
}
