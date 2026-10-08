import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { ProjectCard } from "@/components/content/Cards";
import { Container } from "@/components/layout/Container";
import { getProjects } from "@/lib/api";
import { pageMetadata } from "@/lib/content";

export const revalidate = 300;
export const metadata = pageMetadata(
  "Проекты",
  "Проекты BKS Lab: продукты, сервисы и открытые разработки.",
  "/projects",
);

export default async function ProjectsPage() {
  const projects = await getProjects();
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={[{ title: "Проекты" }]} />
      <header className="mb-12 max-w-3xl">
        <p className="eyebrow mb-4">ОТ ИДЕИ К РЕЗУЛЬТАТУ</p>
        <h1 className="page-title">Мои проекты</h1>
        <p className="mt-5 text-text-muted">
          Продукты и сервисы, в которых технологии решают задачи людей.
          Архитектура, подходы и опыт разработки.
        </p>
      </header>
      <div className="card-grid">
        {projects.map((project) => (
          <ProjectCard key={project.slug} project={project} heading="h2" />
        ))}
      </div>
      {!projects.length && (
        <p className="empty-state">Проекты скоро появятся.</p>
      )}
    </Container>
  );
}
