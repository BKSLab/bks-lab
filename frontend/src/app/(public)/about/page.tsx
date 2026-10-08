import Link from "next/link";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { Container } from "@/components/layout/Container";
import { pageMetadata } from "@/lib/content";

export const metadata = pageMetadata(
  "Обо мне",
  "Об авторе BKS Lab: опыт, направления работы и подходы.",
  "/about",
);

export default function AboutPage() {
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={[{ title: "Обо мне" }]} />
      <div className="max-w-3xl">
        <p className="eyebrow mb-4">ЧЕЛОВЕК ЗА ПРОЕКТАМИ</p>
        <h1 className="page-title">Обо мне</h1>
        <p className="mt-6 text-xl text-text-muted">
          BKS Lab — личное пространство для проектов, практики разработки и
          мыслей о технологиях.
        </p>
        <section className="mt-12 border-t border-border pt-8">
          <h2 className="text-2xl font-semibold">Что здесь можно найти</h2>
          <p className="mt-4 text-text-muted">
            Разработку, архитектуру, управление IT-проектами, искусственный
            интеллект и доступность. Опыт и идеи, которыми хочется поделиться.
          </p>
        </section>
        <section className="mt-10 border-t border-border pt-8">
          <h2 className="text-2xl font-semibold">Об авторе</h2>
          <p className="mt-4 text-text-muted">
            Подробный рассказ об опыте и пути автора готовится. А пока
            познакомиться с работой BKS Lab можно через проекты и публикации.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/projects" className="button-primary">
              Мои проекты
            </Link>
            <Link href="/blog" className="button-secondary">
              Читать блог
            </Link>
          </div>
        </section>
      </div>
    </Container>
  );
}
