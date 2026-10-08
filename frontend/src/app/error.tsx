"use client";

import { Container } from "@/components/layout/Container";
import { PublicShell } from "@/components/layout/PublicShell";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <PublicShell>
      <Container className="py-16">
        <section role="alert">
          <h1 className="text-4xl font-bold">Что-то пошло не так</h1>
          <p className="mt-4 max-w-prose text-text-muted">
            Произошла ошибка при загрузке страницы. Попробуйте обновить её.
          </p>
          {error.digest ? (
            <p className="mt-2 font-mono text-sm text-text-muted">
              Код ошибки: {error.digest}
            </p>
          ) : null}
          <p className="mt-6">
            <button
              type="button"
              onClick={reset}
              className="inline-flex min-h-11 items-center rounded-[var(--radius-button)] bg-accent px-6 py-2 text-sm font-semibold text-on-accent hover:bg-accent-hover"
            >
              Попробовать снова
            </button>
          </p>
        </section>
      </Container>
    </PublicShell>
  );
}
