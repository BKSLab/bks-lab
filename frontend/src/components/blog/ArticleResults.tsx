import { ArticleCard } from "@/components/content/Cards";
import { Pagination } from "@/components/content/Pagination";
import type { ArticleSummary, Paged } from "@/lib/api/types";

export function ArticleResults({
  data,
  base,
}: {
  data: Paged<ArticleSummary>;
  base: string;
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
          В этом разделе пока нет статей.
        </p>
      )}
      <Pagination
        base={base}
        page={data.page}
        pages={data.pages}
      />
    </>
  );
}
