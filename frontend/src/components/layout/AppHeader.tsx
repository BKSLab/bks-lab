import Link from "next/link";

import { Container } from "@/components/layout/Container";
import { BrandLogo } from "@/components/layout/BrandLogo";
import { ArrowRightIcon } from "@/components/ui/icons";
import { MainNavigation } from "@/components/navigation/MainNavigation";
import { MobileNavigation } from "@/components/navigation/MobileNavigation";
import { SearchButton } from "@/components/navigation/SearchButton";
import { ThemeToggle } from "@/components/navigation/ThemeToggle";

export function AppHeader() {
  return (
    <header className="border-b border-border bg-surface">
      <Container className="relative flex min-h-20 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3">
        <Link
          href="/"
          aria-label="BKS Lab — на главную"
          className="inline-flex min-h-11 items-center"
        >
          <BrandLogo />
        </Link>
        <MainNavigation className="hidden min-w-0 max-w-full desktop:block" />
        <div className="flex max-w-full flex-wrap items-center gap-1">
          <SearchButton />
          <ThemeToggle />
          <Link
            href="/contacts"
            className="header-contact hidden desktop:inline-flex"
          >
            Связаться <ArrowRightIcon className="h-4 w-4" />
          </Link>
          <MobileNavigation />
        </div>
      </Container>
    </header>
  );
}
