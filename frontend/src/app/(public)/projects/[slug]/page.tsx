import Image from "next/image";
import Link from "next/link";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { Tags } from "@/components/content/Cards";
import { ContentHtml } from "@/components/content/ContentHtml";
import { Container } from "@/components/layout/Container";
import { getProject, getProjects } from "@/lib/api";
import { pageMetadata } from "@/lib/content";

export const revalidate = 300;
export const dynamicParams = true;
type Props = { params: Promise<{ slug: string }> };

export async function generateStaticParams() {
  return (await getProjects()).map((project) => ({ slug: project.slug }));
}

export async function generateMetadata({ params }: Props) {
  const project = await getProject((await params).slug);
  return pageMetadata(
    project.seo.title || project.title,
    project.seo.description || project.excerpt,
    `/projects/${project.slug}`,
    project.seo.og_image || "/og/bks-lab-default.jpg",
  );
}

export default async function ProjectPage({ params }: Props) {
  const project = await getProject((await params).slug);
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs
        items={[
          { title: "Проекты", href: "/projects" },
          { title: project.title },
        ]}
      />
      <article className="mx-auto max-w-[72ch]">
        <header className="mb-10">
          <p className="eyebrow mb-4">
            {project.status === "active"
              ? "ПРОЕКТ / В РАЗВИТИИ"
              : "ПРОЕКТ / АРХИВ"}
          </p>
          <h1 className="page-title">{project.title}</h1>
          <p className="my-6 text-xl text-text-muted">{project.excerpt}</p>
          <Tags tags={project.tags} />
        </header>
        <Image
          src={project.cover_image}
          alt=""
          width={1200}
          height={750}
          sizes="(min-width: 1100px) 800px, 100vw"
          className="mb-10 h-auto w-full rounded-card"
        />
        <ContentHtml html={project.content_html} />
        <footer className="mt-12 border-t border-border pt-6">
          <Link href="/projects" className="text-link">
            ← Все проекты
          </Link>
        </footer>
      </article>
    </Container>
  );
}
