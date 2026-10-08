"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { ArticleSummary, Paged } from "@/lib/api/types";
import { ARTICLE_PAGE_SIZE, pageHref, pageNumber } from "@/lib/content";
import { ArticleResults } from "./ArticleResults";

type SearchResult = {
  key: string;
  data?: Paged<ArticleSummary>;
  error?: string;
};

export function BlogSearch({
  initial,
  base,
  category,
}: {
  initial: Paged<ArticleSummary>;
  base: string;
  category?: string;
}) {
  const params = useSearchParams();
  const router = useRouter();
  const query = (params.get("q") ?? "").trim();
  const page = pageNumber(params.get("page") ?? "1") ?? 1;
  const key = JSON.stringify([query, page, category]);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [validation, setValidation] = useState("");
  const [retry, setRetry] = useState(0);
  const valid = query.length >= 2 && query.length <= 100;
  const loading = valid && result?.key !== key;

  useEffect(() => {
    if (!valid) return;
    let active = true;
    const search = new URLSearchParams({
      q: query,
      page: String(page),
      page_size: String(ARTICLE_PAGE_SIZE),
    });
    if (category) search.set("category", category);
    apiFetch<Paged<ArticleSummary>>(`/articles?${search}`, {
      tags: ["articles"],
    }).then(
      (data) => {
        if (active) setResult({ key, data });
      },
      () => {
        if (active)
          setResult({
            key,
            error: "Не удалось выполнить поиск. Попробуйте ещё раз.",
          });
      },
    );
    return () => {
      active = false;
    };
  }, [query, page, category, key, valid, retry]);

  const error =
    validation || (query && !valid ? "Введите от 2 до 100 символов." : "");
  return (
    <div>
      <form
        role="search"
        noValidate
        className="mb-6"
        onSubmit={(event) => {
          event.preventDefault();
          const input = event.currentTarget.elements.namedItem(
            "q",
          ) as HTMLInputElement;
          const value = input.value.trim();
          if (value && (value.length < 2 || value.length > 100)) {
            setValidation("Введите от 2 до 100 символов.");
            input.focus();
            return;
          }
          setValidation("");
          router.push(value ? pageHref(base, 1, value) : base, {
            scroll: false,
          });
        }}
      >
        <label htmlFor="blog-search" className="mb-2 block text-sm font-medium">
          Поиск по статьям
        </label>
        <div className="flex flex-wrap gap-3">
          <input
            key={query}
            id="blog-search"
            name="q"
            type="search"
            defaultValue={query}
            minLength={2}
            maxLength={100}
            className="form-field min-w-0 flex-1"
            placeholder="Тема, технология или идея"
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "blog-search-error" : undefined}
            onChange={() => setValidation("")}
          />
          <button type="submit" className="button-primary">
            Найти
          </button>
        </div>
        {error && (
          <p
            id="blog-search-error"
            role="alert"
            className="mt-2 text-sm text-error"
          >
            {error}
          </p>
        )}
      </form>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <p role="status" aria-live="polite" className="text-sm text-text-muted">
          {query
            ? loading
              ? "Ищем статьи…"
              : result?.key === key && result.data
                ? `Найдено статей: ${result.data.total}`
                : ""
            : `Статей в разделе: ${initial.total}`}
        </p>
        {query && (
          <Link
            href={base}
            className="text-link"
            onClick={() => setValidation("")}
          >
            Сбросить поиск
          </Link>
        )}
      </div>
      {query ? (
        <div aria-busy={loading}>
          {loading && (
            <p className="empty-state" aria-hidden="true">
              Поиск…
            </p>
          )}
          {result?.key === key && result.error && (
            <div className="empty-state">
              <p role="alert">{result.error}</p>
              <button
                type="button"
                className="text-link mt-3"
                onClick={() => {
                  setResult(null);
                  setRetry((n) => n + 1);
                }}
              >
                Повторить поиск
              </button>
            </div>
          )}
          {valid && result?.key === key && result.data && (
            <ArticleResults data={result.data} base={base} query={query} />
          )}
        </div>
      ) : (
        <ArticleResults data={initial} base={base} />
      )}
    </div>
  );
}
