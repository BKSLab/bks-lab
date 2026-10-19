import Image from "next/image";
import Link from "next/link";
import { Container } from "@/components/layout/Container";
import {
  ArticleCard,
  ProjectCard,
} from "@/components/content/Cards";
import { NotesFeed } from "@/components/content/NotesFeed";
import { SectionHeading } from "@/components/content/SectionHeading";
import {
  AccessibilityIcon,
  AiIcon,
  ArrowRightIcon,
  CodeIcon,
  ManagementIcon,
} from "@/components/ui/icons";
import { getLatestArticles, getNotesFeed, getProjects } from "@/lib/api";

const directions = [
  {
    title: "Разработка",
    text: "От идеи до работающего продукта.",
    Icon: CodeIcon,
  },
  {
    title: "Управление",
    text: "Процессы, команда, результат.",
    Icon: ManagementIcon,
  },
  { title: "AI", text: "Практика, наблюдения, возможности.", Icon: AiIcon },
  {
    title: "Люди",
    text: "Доступность, инклюзия, развитие.",
    Icon: AccessibilityIcon,
  },
];

export async function HomeContent() {
  const [projects, articles, notes] = await Promise.all([
    getProjects({ featured: true }),
    getLatestArticles(3),
    getNotesFeed({ limit: 5 }),
  ]);
  return (
    <>
      <div className="home-intro">
        <section aria-labelledby="home-title" className="home-hero dark-panel">
          <div className="hero-art" aria-hidden="true">
            <Image
              src="/images/hero/bks-lab-wall.webp"
              alt=""
              fill
              sizes="100vw"
              loading="eager"
              fetchPriority="high"
            />
          </div>
          <Container className="home-hero-inner">
            <div className="hero-copy">
              <h1 id="home-title" className="home-title">
                Проверяю идеи на практике.
              </h1>
              <p className="mt-6 text-lg leading-relaxed text-text-muted">
                Эксперименты с AI, собственные инструменты и новости технологий —
                с авторским разбором и выводами.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/projects" className="button-primary">
                  Мои проекты <ArrowRightIcon className="h-4 w-4" />
                </Link>
                <Link href="/blog" className="button-secondary">
                  Читать блог
                </Link>
              </div>
            </div>
          </Container>
        </section>
        <Container>
          <section
            aria-labelledby="directions-title"
            className="directions-strip"
          >
            <h2 id="directions-title" className="sr-only">
              Направления
            </h2>
            <ul className="directions-grid">
              {directions.map(({ title, text, Icon }) => (
                <li key={title} className="direction-item">
                  <Icon className="h-7 w-7 shrink-0 text-accent" />
                  <div>
                    <h3 className="text-xl font-semibold">{title}</h3>
                    <p className="mt-1 text-sm text-text-muted">{text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </Container>
      </div>
      <Container className="home-columns">
        <div className="home-main">
          <section className="section-space">
            <SectionHeading
              title="Мои проекты"
              href="/projects"
              linkText="Все проекты"
            />
            <div className="card-grid">
              {projects.map((project) => (
                <ProjectCard key={project.slug} project={project} />
              ))}
            </div>
            {!projects.length && (
              <p className="empty-state">Проекты скоро появятся.</p>
            )}
          </section>
          <section className="section-space border-t border-border">
            <SectionHeading
              title="Последние статьи"
              href="/blog"
              linkText="Все статьи"
            />
            <div className="card-grid">
              {articles.map((article) => (
                <ArticleCard key={article.slug} article={article} />
              ))}
            </div>
            {!articles.length && (
              <p className="empty-state">Статьи скоро появятся.</p>
            )}
          </section>
        </div>
        <aside aria-labelledby="home-notes-title" className="home-notes">
          <h2 id="home-notes-title" className="mb-5 text-2xl font-bold">
            Заметки на полях
          </h2>
          <NotesFeed initialFeed={notes} compact pageSize={5} />
          <Link href="/notes" className="text-link mt-3">
            Все заметки <ArrowRightIcon className="h-4 w-4" />
          </Link>
        </aside>
      </Container>
    </>
  );
}
