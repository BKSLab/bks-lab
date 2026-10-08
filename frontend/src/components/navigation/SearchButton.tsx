import Link from "next/link";

import { SearchIcon } from "@/components/ui/icons";

// Leads to /blog, where the search UI lives (implementation plan, stage 4).
export function SearchButton() {
  return (
    <Link
      href="/blog"
      aria-label="Поиск по блогу"
      className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-text-muted hover:text-accent"
    >
      <SearchIcon className="h-5 w-5" />
    </Link>
  );
}
