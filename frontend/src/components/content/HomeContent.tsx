import Image from "next/image";
import Link from "next/link";
import { Container } from "@/components/layout/Container";
import {
  ArticleCard,
  NotePreview,
  ProjectCard,
} from "@/components/content/Cards";
import { SectionHeading } from "@/components/content/SectionHeading";
import {
  AccessibilityIcon,
  AiIcon,
  ArrowRightIcon,
  CodeIcon,
  ManagementIcon,
} from "@/components/ui/icons";
import { getLatestArticles, getLatestNotes, getProjects } from "@/lib/api";

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
    getLatestNotes(3),
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
              <p className="eyebrow mb-6">РАЗРАБОТКА · ПРОЕКТЫ · ИДЕИ</p>
              <h1 id="home-title" className="home-title">
                Технологии для более{" "}
                <span className="text-accent">открытого мира</span>
              </h1>
              <p className="mt-6 max-w-prose text-lg text-text-muted">
                Разработка. Управление. Искусственный интеллект. Идеи, которые
                работают.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/projects" className="button-primary">
                  Мои проекты <ArrowRightIcon className="h-4 w-4" />
                </Link>
                <Link href="/blog" className="button-secondary">
                  Читать блог
                </Link>
              </div>
              <p aria-hidden="true" className="hero-signature">
                TECHNOLOGY FOR A MORE OPEN WORLD
              </p>
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
      <Container>
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
        <section className="section-space border-t border-border">
          <SectionHeading
            title="Заметки на полях"
            href="/notes"
            linkText="Все заметки"
          />
          <div className="grid gap-x-8 md:grid-cols-2 desktop:grid-cols-3">
            {notes.map((note) => (
              <NotePreview key={note.slug} note={note} />
            ))}
          </div>
          {!notes.length && (
            <p className="empty-state">Заметки скоро появятся.</p>
          )}
        </section>
      </Container>
      <section className="statement dark-panel">
        <Container>
          <div className="statement-inner">
            <blockquote className="max-w-3xl border-l-2 border-accent pl-6 md:pl-10">
              <p className="text-3xl leading-snug font-semibold md:text-4xl">
                Технологии ценны, когда они делают жизнь людей лучше.
              </p>
              <footer className="mt-6 font-mono text-sm text-accent">
                — BKS Lab
              </footer>
            </blockquote>
            <Link href="/about" className="button-secondary shrink-0">
              Обо мне <ArrowRightIcon className="h-4 w-4" />
            </Link>
          </div>
        </Container>
      </section>
    </>
  );
}
