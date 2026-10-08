import { ArticleCard } from "@/components/content/Cards";
import { Pagination } from "@/components/content/Pagination";
import type { ArticleSummary, Paged } from "@/lib/api/types";

export function ArticleResults({
  data,
  base,
  query,
}: {
  data: Paged<ArticleSummary>;
  base: string;
  query?: string;
}) {
  return (
    <>
      <div className="space-y-6">
        {data.items.map((article) => (
          <ArticleCard article={article} key={article.slug} list />
        ))}
      </div>
      {!data.items.length && (
        <p className="empty-state">
          {query
            ? "Ничего не найдено. Попробуйте другое слово или сбросьте поиск."
            : "В этом разделе пока нет статей."}
        </p>
      )}
      <Pagination
        base={base}
        page={data.page}
        pages={data.pages}
        query={query}
      />
    </>
  );
}
