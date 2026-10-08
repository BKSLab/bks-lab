import { Suspense } from "react";

import { AppFooter } from "@/components/layout/AppFooter";
import { AppHeader } from "@/components/layout/AppHeader";
import { SkipLink } from "@/components/layout/SkipLink";
import { PageViewTracker } from "@/components/tracking/PageViewTracker";

export function PublicShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SkipLink />
      <AppHeader />
      <main id="main-content" tabIndex={-1} className="flex-1">
        {children}
      </main>
      <AppFooter />
      <Suspense fallback={null}>
        <PageViewTracker />
      </Suspense>
    </>
  );
}
